from __future__ import annotations
import requests
from typing import Any, Dict, List
from .config import ODDS_API_KEY, BOOKS

BASE_URL = "https://api.the-odds-api.com/v4"

def fetch_odds_for_sport(sport_key: str, regions: str = "us", markets: str = "h2h,spreads,totals", date_format: str = "iso") -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        raise RuntimeError("Missing ODDS_API_KEY in environment or secrets.")
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
        "dateFormat": date_format,
        "bookmakers": ",".join(BOOKS) if BOOKS else None,
    }
    # Remove None params for cleanliness
    params = {k: v for k, v in params.items() if v is not None}
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()
