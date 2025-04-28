# scraper/debug_api.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
import sqlite3, pathlib, json, datetime, asyncio, os

from scraper.race_job import scrape_race          # ← existing coroutine
from scraper.storage import store_snapshot        # if you want to persist
DB_DIR  = pathlib.Path("/app/data")
DB_FILE = DB_DIR / "horse_bets.sqlite"
DB_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

# ---------- helpers -------------------------------------------------------- #
def _latest_row():
    conn = sqlite3.connect(DB_FILE)
    row  = conn.execute(
        "SELECT race_pk, payload FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row

# ---------- routes --------------------------------------------------------- #
@app.get("/latest")
def latest_snapshot():
    row = _latest_row()
    if not row:
        return {"error": "no snapshots yet",
                "server_time": datetime.datetime.utcnow().isoformat()}
    pk, payload = row
    data = json.loads(payload)
    data["race_pk"] = pk
    return data


@app.post("/scrape/{race_id}")
async def scrape_now(
    race_id: str,
    background: BackgroundTasks,
):
    """
    Trigger scrape_race(race_id) immediately in the background and
    return 202 Accepted with a tiny status blob.
    """
    # Kick off the coroutine without blocking the response
    background.add_task(_run_and_store, race_id)
    return {"status": "accepted", "race_id": race_id, "ts": datetime.datetime.utcnow().isoformat()}


async def _run_and_store(race_id: str):
    """Helper that calls scrape_race and stores the snapshot."""
    payload = await scrape_race(race_id)          # returns dict from bookmarklet
    store_snapshot(race_id, payload)              # persist so /latest can see it
