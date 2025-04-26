# scraper/race_job.py
"""
scrape_race(race_id)  – runs 3 min before post-time

1. Opens the Turf day-card.
2. Clicks the tile whose data-betting-race-id matches race_id.
3. Waits for the race view to render.
4. Executes the bookmarklet JS and stores a JSON snapshot.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from scraper.browser import get_page
from scraper.storage import store_snapshot

log = logging.getLogger(__name__)

# Same JS you already used (feel free to adjust fields)
BOOKMARK_JS = """
() => {
  const title   = document.querySelector('.race-head-title')?.innerText.trim() || '';
  const meta    = document.querySelector('.race-info')?.innerText.trim() || '';
  const runners = [...document.querySelectorAll('.runners-list')].map(el => el.outerHTML).join('\\n');
  const track   = document.querySelector('.meeting-title')?.innerText.trim() || '';
  return { title, meta, runners, track };
}
"""


async def scrape_race(race_id: str) -> None:
    """Click the tile, harvest DOM, persist snapshot."""
    log.info("Scraping race_id=%s", race_id)

    async with get_page() as page:
        # 1. Go to the daily card
        await page.goto("https://www.unibet.fr/turf", wait_until="networkidle")

        tile_selector = f'li.race[data-betting-race-id="{race_id}"]'
        await page.wait_for_selector(tile_selector, timeout=10_000)

        # 2. Click the tile
        await page.click(tile_selector)

        # 3. Wait until a race-specific element appears
        await page.wait_for_selector(".race-head-title", timeout=10_000)

        # 4. Extract data and store
        payload = await page.evaluate(BOOKMARK_JS)
        payload["scraped_at"] = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

        payload["race_id"] = race_id      # add external id into the blob
        store_snapshot(race_id, payload)
        log.info("Snapshot stored for race_id=%s", race_id)
