from __future__ import annotations
import os
from dotenv import load_dotenv

# Try to read from Streamlit secrets if available
def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st  # type: ignore
        return str(st.secrets.get(key, default))
    except Exception:
        return default

load_dotenv()

def _env_or_secret(key: str, default: str = "") -> str:
    # Priority: env var (local .env) -> Streamlit secrets -> default
    v = os.getenv(key)
    if v is not None and v != "":
        return v
    v = _get_secret(key, default)
    return v if v != "" else default

ODDS_API_KEY: str = _env_or_secret("ODDS_API_KEY", "")
BOOKS = [b.strip() for b in _env_or_secret("BOOKS", "fliff,betmgm,draftkings,fanduel,caesars").split(",") if b.strip()]
SPORTS = [s.strip() for s in _env_or_secret("SPORTS", "mlb,wnba,mls").split(",") if s.strip()]
PARLAY_MAX_LEGS = int(_env_or_secret("PARLAY_MAX_LEGS", "4") or "4")
KELLY_FRACTION = float(_env_or_secret("KELLY_FRACTION", "0.25") or "0.25")
EDGE_A = float(_env_or_secret("EDGE_A_THRESHOLD", "2.5") or "2.5")
EDGE_B = float(_env_or_secret("EDGE_B_THRESHOLD", "1.0") or "1.0")
