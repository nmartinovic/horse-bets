"""
Shared APScheduler instance (AsyncIO flavour) + persistent job store.
"""
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scraper.daily import collect_today

JOB_DB = Path(__file__).resolve().parent.parent / "data" / "jobs.sqlite"
JOB_DB.parent.mkdir(parents=True, exist_ok=True)

SCHED = AsyncIOScheduler(
    timezone=ZoneInfo("Europe/Paris"),
    jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{JOB_DB}")},
)

# Daily 09:00 card‑scrape
SCHED.add_job(
    collect_today,          # no args
    "cron",
    hour=9,
    minute=0,
    id="collect_today",
    replace_existing=True,
)