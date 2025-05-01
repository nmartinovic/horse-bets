# scraper/daily.py
"""
collect_today(sched=None)
─────────────────────────
• Scrapes today's Unibet Turf card (all race tiles, scrolling as needed)
• Upserts each race_id + post_time into SQLite
• Queues a one-off scrape_race() job 3 minutes before post-time

Run once manually:
    poetry run python -m scraper.daily
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import tomli
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper.browser import get_page
from scraper.storage import upsert_race
from scraper import race_job

# --------------------------------------------------------------------------- #
# Config & constants
# --------------------------------------------------------------------------- #
TZ = ZoneInfo("Europe/Paris")
CFG = tomli.load(open("config.toml", "rb"))

LIST_SEL: str = "[data-betting-race-id]"                 # robust attribute
TIME_SEL: str = CFG["turf"]["time_selector"]             # ".countdown"
CARD_URL: str = CFG["turf"]["card_url"]                  # https://www.unibet.fr/turf

# --------------------------------------------------------------------------- #
# Main task
# --------------------------------------------------------------------------- #
async def collect_today(sched: AsyncIOScheduler | None = None) -> None:
    if sched is None:                       # called by the global scheduler
        from scraper.scheduler import SCHED as sched  # late import

    # ── 1. Scrape the day card ───────────────────────────────────────────────
    async with get_page() as page:
        await page.goto(CARD_URL, wait_until="networkidle")

        # cookie consent (FR locale)
        try:
            await page.locator("button:has-text('Accepter')").click(timeout=3_000)
        except Exception:  # noqa: BLE001
            pass  # banner not present

        # wait for at least one tile
        await page.wait_for_selector(LIST_SEL, timeout=30_000)

        # scroll until no new tiles appear
        last_count = 0
        while True:
            tiles = await page.query_selector_all(LIST_SEL)
            if len(tiles) == last_count:
                break
            last_count = len(tiles)
            await tiles[-1].scroll_into_view_if_needed()
            await page.wait_for_timeout(800)      # give JS time to load

        # extract ids + HHhMM strings from *all* tiles
        JS = """
        (elements, timeSel) => elements.map(el => {
            const id   = el.dataset.bettingRaceId;
            const time = el.querySelector(timeSel)?.innerText.trim() || null;
            return { id, time };
        })
        """
        races = await page.eval_on_selector_all(LIST_SEL, JS, TIME_SEL)
        logger.info("Harvested %d race tiles", len(races))

    # ── 2. Store + schedule ─────────────────────────────────────────────────
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
    async def _run_once():
        tmp_sched = AsyncIOScheduler(timezone=TZ)
        tmp_sched.start()
        await collect_today(tmp_sched)
        tmp_sched.shutdown(wait=False)

    asyncio.run(_run_once())
