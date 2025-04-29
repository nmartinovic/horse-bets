# scraper/debug_api.py  (only the top section changes)

import json, pathlib, sqlite3, asyncio, datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from scraper.daily import collect_today
from scraper.race_job import scrape_race
from scraper.storage import ENGINE, Base
import logging

DB_DIR  = pathlib.Path("/app/data")
DB_FILE = DB_DIR / "horse_bets.sqlite"          # <- point at the FILE

DB_DIR.mkdir(parents=True, exist_ok=True)       # ensure directory exists
if not DB_FILE.exists():                       # bootstrap empty DB
    Base.metadata.create_all(ENGINE)

app = FastAPI(title="Horse-Bets Debug API")

# ------------- helper -----------------------------------------------------
def latest_snapshot():
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT id, race_id, payload "
        "FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    snap_id, race_id, payload = row
    data = json.loads(payload)
    data.update({"snapshot_id": snap_id, "race_id": race_id})
    return data


# ------------------------------------------------------------------ routes
@app.get("/latest")
def latest():
    data = latest_snapshot()
    return data or {"error": "no snapshots yet",
                    "server_time": datetime.datetime.utcnow().isoformat()}

@app.post("/collect")
async def run_collect(bg: BackgroundTasks):
    async def _task():
        await collect_today(None)           # tmp_sched=None → just harvest IDs
    bg.add_task(_task)
    return {"status": "collect_today queued"}

@app.post("/scrape/{race_id}")
async def run_scrape(race_id: str, bg: BackgroundTasks):
    async def _task():
        await scrape_race(race_id)
    bg.add_task(_task)
    return {"status": f"scrape_race({race_id}) queued"}

# ------------------------------------------------------------------ lifespan
@app.on_event("startup")
async def announce():
    logging.info("Debug API ready – /latest, /collect, /scrape/{id}")
