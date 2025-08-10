from __future__ import annotations
import os, sys
# make local folder importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

import datetime as dt
import pandas as pd
import streamlit as st

from config import SPORTS, KELLY_FRACTION, EDGE_A, EDGE_B, PARLAY_MAX_LEGS
from odds_api import fetch_odds_for_sport
from selection import build_straight_picks, build_parlays
from reasoning import explain_pick

st.set_page_config(page_title="Fliff Picks Copilot", page_icon="🎯", layout="wide")
st.title("🎯 Fliff Picks Copilot — v1 (Cloud)")

today = dt.date.today()
st.caption(f"Today: {today.isoformat()} — This v1 uses market no‑vig fair probabilities. Add your own model in v2.")

sports = st.multiselect("Sports", options=SPORTS, default=SPORTS)

bankroll_units = st.number_input("Bankroll (units)", min_value=10, max_value=10000, value=100, step=10)
kelly_fraction = st.slider("Kelly fraction", 0.0, 1.0, float(KELLY_FRACTION), 0.05)

if st.button("Fetch today’s slate & build picks"):
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
                )
                for p in picks:
                    p["explanation"] = explain_pick(p)
                all_picks.extend(picks)

    if not all_picks:
        st.warning("No picks generated — try different sports or confirm your API key/books in app secrets.")
    else:
        df = pd.DataFrame(all_picks)
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

st.divider()
st.caption("For informational/educational use. Play responsibly.")
