import json, pathlib, sqlite3, datetime, asyncio, logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from scraper.daily import collect_today
from scraper.race_job import scrape_race
from scraper.storage import ENGINE, Base

# ─── database bootstrap ─────────────────────────────────────────────
DB_DIR  = pathlib.Path("/app/data")
DB_FILE = DB_DIR / "horse_bets.sqlite"
DB_DIR.mkdir(parents=True, exist_ok=True)
if not DB_FILE.exists():
    Base.metadata.create_all(ENGINE)

# ─── lifespan: launch head-less scraper in background ───────────────
async def lifespan(app: FastAPI):
    from main import main_async          # root-level main.py
    asyncio.create_task(main_async())
    logging.info("Background scraper started alongside FastAPI")
    yield                                # nothing to clean on shutdown

# ─── create the *single* FastAPI instance first ─────────────────────
app = FastAPI(title="Horse-Bets Debug API", lifespan=lifespan)

# ─── helper ----------------------------------------------------------
def latest_snapshot():
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        "SELECT id, race_id, payload FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    snap_id, race_id, payload = row
    data = json.loads(payload)
    data.update({"snapshot_id": snap_id, "race_id": race_id})
    return data

# ─── routes ----------------------------------------------------------
@app.get("/latest")
def latest():
    data = latest_snapshot()
    return data or {
        "error": "no snapshots yet",
        "server_time": datetime.datetime.utcnow().isoformat(),
    }

@app.get("/races")
def list_races(limit: int | None = 50):
    sql = (
        "SELECT id, race_id, time(post_time) AS local_time "
        "FROM races WHERE date(post_time)=? ORDER BY post_time "
    )
    if limit:
        sql += f"LIMIT {limit}"
    rows = sqlite3.connect(DB_FILE).execute(
        sql, (datetime.date.today().isoformat(),)
    ).fetchall()
    return [{"pk": r[0], "race_id": r[1], "post_time": r[2]} for r in rows]

@app.post("/collect")
async def run_collect(bg: BackgroundTasks):
    async def _task():
        await collect_today(None)
    bg.add_task(_task)
    return {"status": "collect_today queued"}

@app.post("/scrape/{race_id}")
async def run_scrape(race_id: str, bg: BackgroundTasks):
    async def _task():
        await scrape_race(race_id)
    bg.add_task(_task)
    return {"status": f"scrape_race({race_id}) queued"}
