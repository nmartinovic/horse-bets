# scraper/daily.py
"""
Harvest today's Unibet turf card, store every race in SQLite,
and queue a scrape_race() job T-3 min before post-time.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import tomli
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper.browser import get_page
from scraper.storage import upsert_race
from scraper import race_job

# ────────────────────── logging ───────────────────────────────────────────
logger = logging.getLogger("daily")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# ────────────────────── config ────────────────────────────────────────────
TZ = ZoneInfo("Europe/Paris")
CFG = tomli.load(open("config.toml", "rb"))

CARD_URL: str = CFG["turf"]["card_url"]          # https://www.unibet.fr/turf
TIME_SEL: str = CFG["turf"]["time_selector"]     # ".countdown"
LIST_SEL: str = "[data-betting-race-id]"         # robust selector

TIME_RE = re.compile(r"^\s*(\d{1,2})h(\d{2})\s*$")   # 9h05, 13h58, 24h15 …

# ────────────────────── main task ─────────────────────────────────────────
async def collect_today(sched: AsyncIOScheduler | None = None) -> None:
    """Scrape today's race tiles and schedule T-3 scrapes."""
    if sched is None:          # called by global scheduler
        from scraper.scheduler import SCHED as sched  # late import to avoid cycle

    async with get_page() as page:
        await page.goto(CARD_URL, wait_until="networkidle")

        # Accept cookie banner if present
        try:
            await page.locator("button:has-text('Accepter')").click(timeout=3_000)
        except Exception:  # noqa: BLE001
            pass

        await page.wait_for_selector(LIST_SEL, timeout=30_000)

        # Scroll until no new tiles appear (lazy-load)
        last = 0
        while True:
            tiles = await page.query_selector_all(LIST_SEL)
            if len(tiles) == last:
                break
            last = len(tiles)
            await tiles[-1].scroll_into_view_if_needed()
            await page.wait_for_timeout(800)

        # Extract race_id + raw time text from ALL tiles
        JS = """
        (elements, timeSel) => elements.map(el => {
            const id   = el.dataset.bettingRaceId;
            const time = el.querySelector(timeSel)?.innerText.trim() || null;
            return { id, time };
        })
        """
        races = await page.eval_on_selector_all(LIST_SEL, JS, TIME_SEL)
        logger.info("Harvested %d race tiles", len(races))

    # ── store + schedule ───────────────────────────────────────────────────
    today: date = datetime.now(TZ).date()

    for r in races:
        m = TIME_RE.match(r["time"] or "")
        if not m:
            logger.warning("Skipping tile with bad time string: %s", r["time"])
            continue

        hh, mm = map(int, m.groups())
        post_day = today
        if hh == 24:           # Unibet sometimes shows 24hXX for after-midnight
            hh = 0
            post_day += timedelta(days=1)

        post_dt = datetime(post_day.year, post_day.month, post_day.day,
                           hh, mm, tzinfo=TZ)

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

# ────────────────────── CLI helper (run once) ────────────────────────────
if __name__ == "__main__":
    async def _run_once() -> None:
        tmp = AsyncIOScheduler(timezone=TZ)
        tmp.start()
        await collect_today(tmp)
        tmp.shutdown(wait=False)

    asyncio.run(_run_once())
