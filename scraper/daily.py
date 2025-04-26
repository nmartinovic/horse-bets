# scraper/daily.py
"""
collect_today(sched=None)
─────────────────────────
• Scrapes today's Unibet Turf card (list of race tiles)
• Upserts each race_id + post_time into SQLite
• Queues a one-off scrape_race() job 3 minutes before post-time

If *sched* is None (normal daily run), the function falls back to the
project-wide AsyncIOScheduler imported lazily to avoid circular imports.

Run once manually:
    poetry run python -m scraper.daily
"""
from __future__ import annotations

import tomli
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper.browser import get_page
from scraper.storage import upsert_race
from scraper import race_job

# --------------------------------------------------------------------------- #
# Config & constants
# --------------------------------------------------------------------------- #
TZ = ZoneInfo("Europe/Paris")
CFG = tomli.load(open("config.toml", "rb"))

LIST_SEL = f'{CFG["turf"]["list_selector"]}[data-betting-race-id]'   # "li.race[data-betting-race-id]"
TIME_SEL = CFG["turf"]["time_selector"]                              # ".countdown"

# --------------------------------------------------------------------------- #
# Main task
# --------------------------------------------------------------------------- #
async def collect_today(sched: AsyncIOScheduler | None = None) -> None:
    if sched is None:                      # called by the global scheduler
        from scraper.scheduler import SCHED as sched  # late import

    # 1. Scrape the day-card ---------------------------------------------------
    async with get_page() as page:
        await page.goto(CFG["turf"]["card_url"], wait_until="networkidle")
        await page.wait_for_selector(LIST_SEL, timeout=10_000)

        JS = """
        (els, timeSel) => els.map(el => {
            const id   = el.dataset.bettingRaceId;
            const time = el.querySelector(timeSel)?.innerText.trim() || null;
            return { id, time };
        })
        """
        races = await page.eval_on_selector_all(LIST_SEL, JS, TIME_SEL)

    # 2. Store + schedule ------------------------------------------------------
    today: date = datetime.now(TZ).date()

    for r in races:
        if not r["time"]:
            continue  # skip malformed

        hh, mm = map(int, r["time"].replace("h", ":").split(":"))
        post_dt = datetime(
            year=today.year, month=today.month, day=today.day,
            hour=hh, minute=mm, tzinfo=TZ
        )

        race_id = r["id"]
        upsert_race(race_id, post_dt)

        sched.add_job(
            race_job.scrape_race,
            trigger="date",
            run_date=post_dt - timedelta(minutes=3),
            args=[race_id],
            id=race_id,
            replace_existing=True,
        )

# --------------------------------------------------------------------------- #
# Manual CLI entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import asyncio

    async def _run_once():
        tmp_sched = AsyncIOScheduler(timezone=TZ)
        tmp_sched.start()
        await collect_today(tmp_sched)
        tmp_sched.shutdown(wait=False)

    asyncio.run(_run_once())
