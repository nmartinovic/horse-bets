"""
scraper/debug_api.py  –  lightweight FastAPI debug/ops server
Runs alongside the head-less scraper so you can inspect the DB and
trigger harvests on demand.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import pathlib
import sqlite3
from typing import Any
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile

from scraper.daily import collect_today
from scraper.race_job import scrape_race
from scraper.storage import ENGINE, Base  # to create tables on first run


templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))

# --------------------------------------------------------------------------- #
#  Configuration & DB bootstrap
# --------------------------------------------------------------------------- #
logger = logging.getLogger("debug_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

DB_DIR: pathlib.Path = pathlib.Path("/app/data")          # must match volume mount
DB_FILE: pathlib.Path = DB_DIR / "horse_bets.sqlite"
DB_DIR.mkdir(parents=True, exist_ok=True)
if not DB_FILE.exists():
    logger.info("DB not found – creating schema at %s", DB_FILE)
    Base.metadata.create_all(ENGINE)

# --------------------------------------------------------------------------- #
#  Lifespan hook – start the global scheduler (main_async) once
# --------------------------------------------------------------------------- #
async def lifespan(app: FastAPI):
    from main import main_async   # root-level main.py
    asyncio.create_task(main_async())
    logger.info("Background scraper started alongside FastAPI")
    yield  # nothing special to clean up – container stops via SIGTERM

# --------------------------------------------------------------------------- #
#  Create the (single!) FastAPI app before declaring routes
# --------------------------------------------------------------------------- #
app = FastAPI(title="Horse-Bets Debug API", lifespan=lifespan)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _conn() -> sqlite3.Connection:          # tiny helper
    return sqlite3.connect(DB_FILE)


def latest_snapshot() -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, race_id, payload FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    snap_id, race_id, payload = row
    data = json.loads(payload)
    data.update({"snapshot_id": snap_id, "race_id": race_id})
    return data


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat()}


@app.get("/latest")
def latest():
    data = latest_snapshot()
    return data or {
        "error": "no snapshots yet",
        "server_time": dt.datetime.utcnow().isoformat(),
    }


@app.get("/races")
def list_races(limit: int | None = 50):
    sql = (
        "SELECT id, race_id, time(post_time) AS local_time "
        "FROM races "
        "WHERE date(post_time)=? "
        "ORDER BY post_time "
    )
    if limit:
        sql += f"LIMIT {limit}"
    today = dt.date.today().isoformat()
    with _conn() as conn:
        rows = conn.execute(sql, (today,)).fetchall()
    return [{"pk": r[0], "race_id": r[1], "post_time": r[2]} for r in rows]


@app.post("/collect")
async def run_collect(bg: BackgroundTasks):
    async def _task():
        try:
            await collect_today(None)
        except Exception as exc:  # noqa: BLE001
            logger.exception("collect_today failed: %s", exc)

    bg.add_task(_task)
    return {"status": "collect_today queued"}


@app.post("/scrape/{race_id}")
async def run_scrape(race_id: str, bg: BackgroundTasks):
    async def _task():
        try:
            await scrape_race(race_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scrape_race(%s) failed: %s", race_id, exc)

    bg.add_task(_task)
    return {"status": f"scrape_race({race_id}) queued"}

@app.get("/snapshot/{race_id}")
def snapshot_for_race(race_id: str):
    """
    Return the most-recent snapshot json for the given race_id.
    404 if we’ve never scraped it.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT payload, ts "
            "FROM snapshots "
            "WHERE race_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (race_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="no snapshot for that race")

    payload, ts = row
    data = json.loads(payload)
    data.update({"scraped_at": ts, "race_id": race_id})
    return data

@app.get("/", response_class=HTMLResponse)
def dashboard(req: Request):
    return templates.TemplateResponse("index.html", {"request": req})

# ---------- optional one-shot DB upload helper (comment out after use) -------
"""
@app.post("/upload_db")
async def upload_db(file: UploadFile = File(...)):
    with open(DB_FILE, "wb") as f:
        f.write(await file.read())
    logger.warning("Uploaded DB file – %s bytes", f.tell())
    return {"status": "uploaded", "bytes": f.tell()}
"""
# --------------------------------------------------------------------------- #
