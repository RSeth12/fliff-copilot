from __future__ import annotations
import os, sys
# make local folder importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

import datetime as dt
import pytz
import pandas as pd
import streamlit as st

from .config import KELLY_FRACTION, EDGE_A, EDGE_B, PARLAY_MAX_LEGS
from .odds_api import fetch_odds_for_sport, fetch_sports
from .selection import build_straight_picks, build_parlays, find_near_misses
from reasoning import explain_pick

st.set_page_config(page_title="Fliff Picks Copilot", page_icon="🎯", layout="wide")
st.title("🎯 Fliff Picks Copilot — v1 (Cloud)")

today = dt.date.today()
st.caption(f"Today: {today.isoformat()} — Fair probs from full market; prices from Fliff only.")

# Dynamic sports list from provider
with st.spinner("Loading sports…"):
    try:
        sport_list = fetch_sports()
        all_options = [s["key"] for s in sport_list]
    except Exception as e:
        st.error(f"Could not load sports: {e}")
        all_options = []

sports = st.multiselect("Sports", options=all_options, default=all_options)

bankroll_units = st.number_input("Bankroll (units)", min_value=10, max_value=10000, value=100, step=10)
kelly_fraction = st.slider("Kelly fraction", 0.0, 1.0, float(KELLY_FRACTION), 0.05)

colA, colB = st.columns([1,1])
fetch_clicked = colA.button("Fetch today’s slate & build picks")
refresh_clicked = colB.button("Refresh odds")

if fetch_clicked or refresh_clicked:
    all_picks = []
    for sk in sports:
        with st.spinner(f"Fetching odds for {sk}…"):
            try:
                events = fetch_odds_for_sport(sk)
            except Exception as e:
                st.error(f"Failed to fetch {sk}: {e}")
                continue
            for ev in events:
                if not ev.get("bookmakers") or not ev.get("home_team") or not ev.get("away_team"):
                    continue
                picks = build_straight_picks(
                    ev,
                    kelly_fraction=kelly_fraction,
                    bankroll_units=bankroll_units,
                    edge_A=EDGE_A,
                    edge_B=EDGE_B,
                    price_books=["fliff"],  # <- use only Fliff for displayed odds/pricing
                )
                for p in picks:
                    p["explanation"] = explain_pick(p)
                all_picks.extend(picks)

    if not all_picks:
        st.warning("No picks generated — try different sports or confirm your API key/books in app secrets.")
    else:
        df = pd.DataFrame(all_picks)
        # Convert kickoff to America/New_York
        try:
            df["commence_time"] = pd.to_datetime(df["commence_time"], utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %I:%M %p ET")
        except Exception:
            pass
        cols = [
            "sport_key","commence_time","market","selection","book","odds","decimal",
            "fair_prob","model_prob","edge_pct","ev_per_unit","stake_units","confidence"
        ]
        st.subheader("Top straight picks")
        st.dataframe(df[cols].sort_values(["ev_per_unit","stake_units"], ascending=False), use_container_width=True)

        st.subheader("Parlay ideas")
        parlays = build_parlays(all_picks, conservative_legs=2, balanced_legs=3, fun_max_legs=int(PARLAY_MAX_LEGS))
        if not parlays:
            st.info("Not enough high-quality legs to form parlays today.")
        else:
            for par in parlays:
                st.markdown(f"**{par['name']}** — Combined Dec Odds: `{par['combined_decimal']}` | Est. Hit Prob: `{par['est_hit_prob']}` | Est. EV: `{par['est_ev']}`")
                for leg in par["legs"]:
                    st.write(f"• {leg['selection']} @ {leg['odds']} ({leg['book']})")
                st.caption(par["notes"])

        # Near misses for transparency
        st.subheader("Near misses (just below EV>0)")
        near = find_near_misses(all_picks, ev_floor=-0.02, ev_ceiling=0.0, limit=12)
        if near:
            st.dataframe(pd.DataFrame(near)[["sport_key","commence_time","selection","book","odds","ev_per_unit"]], use_container_width=True)
        else:
            st.caption("None today.")

st.divider()
st.caption("For informational/educational use. Play responsibly.")
