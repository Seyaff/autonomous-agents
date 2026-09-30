import logging
import os
from typing import Any

from langchain.tools import tool
from apify_client import ApifyClient

logger = logging.getLogger(__name__)
_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

ACTOR_ID = "compass/crawler-google-places"


@tool
async def scrape_leads(
    query: str,
    location: str,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Search Google Maps for businesses and return lead info.

    Args:
        query: Business type, e.g. "real estate agencies".
        location: City and country, e.g. "Mildura, Australia".
        max_results: Max leads to return.

    Returns:
        List of lead dicts with name, phone, website, emails, socials.
    """
    run_input = {
        "searchStringsArray": [query],
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": max_results,
        "scrapeContacts": True,       # enables email extraction from website
        "website": "withWebsite",     # skip places without websites
    }
    run = await _client.actor(ACTOR_ID).call(run_input=run_input)
    items = await _client.dataset(run["defaultDatasetId"]).list_items()
    leads = items.items
    logger.info("scrape_leads: %d leads for %r in %r", len(leads), query, location)
    return leads