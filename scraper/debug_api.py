# scraper/debug_api.py
from fastapi import FastAPI
import sqlite3, pathlib, json, datetime

app = FastAPI()
DB = pathlib.Path("/app/data/horse_bets.sqlite")

def row_to_dict(row):
    if not row:
        return None
    pk, payload = row
    data = json.loads(payload)
    data["race_pk"] = pk
    return data

@app.get("/latest")
def latest_snapshot():
    """Return the most-recent snapshot JSON (or 404 if none)."""
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT race_pk, payload FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "no snapshots yet",
                "server_time": datetime.datetime.utcnow().isoformat()}
    return row_to_dict(row)
