# main.py
import asyncio
import logging
from scraper.scheduler import SCHED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

async def main_async():
    """Boot the global scheduler and keep the process alive."""
    SCHED.start()
    # block forever; container will SIGTERM on deploy/scale-down
    await asyncio.Event().wait()          # ← replaces old try/finally block

if __name__ == "__main__":
    asyncio.run(main_async())
