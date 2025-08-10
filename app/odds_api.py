from __future__ import annotations
import os
import requests
from typing import Any, Dict, List
from config import ODDS_API_KEY, BOOKS

BASE_URL = "https://api.the-odds-api.com/v4"

# Per-sport prop allowlists (safe defaults).
SPORT_PROP_KEYS = {
    "baseball": {"player_strikeouts", "player_hits", "player_home_runs", "player_rbis"},
    "basketball": {"player_points", "player_assists", "player_rebounds", "player_three_points_made"},
    "americanfootball": {
        "player_passing_yards", "player_rushing_yards", "player_receiving_yards",
        "player_pass_tds", "player_rush_tds", "player_rec_tds"
    },
    "soccer": {"player_saves", "player_shots_on_target"},
}

BASE_MARKETS = {"h2h", "spreads", "totals"}

def fetch_sports() -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        raise RuntimeError("Missing ODDS_API_KEY in environment or secrets.")
    url = f"{BASE_URL}/sports"
    r = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=20)
    r.raise_for_status()
    return r.json()

def _sport_family(sport_key: str) -> str:
    """
    Map provider sport_key -> family ('baseball','basketball','americanfootball','soccer',...)
    e.g., 'baseball_mlb' -> 'baseball'
    """
    return sport_key.split("_", 1)[0] if "_" in sport_key else sport_key

def _filter_markets_for_sport(sport_key: str, requested: List[str]) -> List[str]:
    fam = _sport_family(sport_key)
    allowed_props = SPORT_PROP_KEYS.get(fam, set())
    out = []
    for m in requested:
        m = m.strip()
        if not m:
            continue
        if m in BASE_MARKETS:
            out.append(m)
        elif m.startswith("player_") and m in allowed_props:
            out.append(m)
        # silently drop unsupported props for this sport
    # fallback baseline if user requested only unsupported props
    return out or list(BASE_MARKETS)

def fetch_odds_for_sport(
    sport_key: str,
    regions: str = "us",
    markets: str | None = None,
    date_format: str = "iso",
) -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        raise RuntimeError("Missing ODDS_API_KEY.")
    # Build market string:
    requested = (os.environ.get("MARKETS") or "").split(",") if markets is None else markets.split(",")
    filtered = _filter_markets_for_sport(sport_key, requested)
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": regions,
        "markets": ",".join(filtered),
        "oddsFormat": "american",
        "dateFormat": date_format,
        "bookmakers": None,
    }
    params = {k: v for k, v in params.items() if v is not None}

    # First attempt with filtered markets
    r = requests.get(url, params=params, timeout=25)
    if r.status_code == 422:
        # Fallback to baseline only (h2h, spreads, totals)
        params["markets"] = ",".join(BASE_MARKETS)
        r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()
