# scraper/daily.py
"""
collect_today(sched) –
• Scrape today’s Unibet-Turf race card at 09:00 Europe/Paris.
• Insert/Update each race row in SQLite.
• Schedule a one-off scrape_race() job 3 minutes before post-time.
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
with open("config.toml", "rb") as f:
    CFG = tomli.load(f)
TZ: ZoneInfo = ZoneInfo("Europe/Paris")

# --------------------------------------------------------------------------- #
# Main task
# --------------------------------------------------------------------------- #


async def collect_today(sched: AsyncIOScheduler) -> None:
    """
    Called by APScheduler at 09:00.  Scrapes today's race list and loads the
    scheduler with one-off jobs that will fire 3 min before each race.
    """
    # --- 1. Pull list of races ------------------------------------------------
    async with get_page() as page:
        await page.goto(CFG["turf"]["card_url"], wait_until="networkidle")

        # Run JS in page context: create {url, time} objects from <li class="race">
        JS = """
        (elements) => elements.map(el => {
            const id = el.dataset.bettingRaceId;
            const url = `https://www.unibet.fr/turf/#/racing/${id}`;
            const timeText = el.querySelector('.countdown')?.innerText.trim() || null;
            return { url, time: timeText };
        })
        """
        races = await page.eval_on_selector_all(CFG["turf"]["list_selector"], JS)

    # --- 2. Store and schedule ------------------------------------------------
    today: date = datetime.now(TZ).date()

    for race in races:
        if not race["time"]:
            # Skip tiles missing a visible time
            continue

        try:
            hh, mm = map(int, race["time"].replace("h", ":").split(":"))
        except ValueError:
            # Unexpected time format (defensive)
            continue

        post_dt = datetime(
            year=today.year,
            month=today.month,
            day=today.day,
            hour=hh,
            minute=mm,
            tzinfo=TZ,
        )

        # DB upsert
        upsert_race(race["url"], post_dt)

        # Schedule T-3 min scrape
        sched.add_job(
            race_job.scrape_race,
            trigger="date",
            run_date=post_dt - timedelta(minutes=3),
            args=[race["url"]],
            id=race["url"],          # unique → safe to replace_existing
            replace_existing=True,
        )
