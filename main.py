# main.py
import asyncio
import logging
from scraper.scheduler import SCHED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

async def main_async() -> None:
    """Start the APScheduler and keep the loop alive forever."""
    SCHED.start()
    logging.info("Scheduler started with %d jobs", len(SCHED.get_jobs()))

    try:
        await asyncio.Event().wait()   # sleep forever (until Ctrl-C)
    finally:
        await SCHED.shutdown()

if __name__ == "__main__":
    asyncio.run(main_async())
