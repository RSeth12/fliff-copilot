# Fliff Picks Copilot (Streamlit Cloud Starter)

Zero-install, browser-only dashboard that fetches today's odds, computes no‑vig fair probabilities,
surfaces straight picks and 2–4 leg parlay ideas, and shows EV/Kelly math.

## Quick Deploy (Streamlit Community Cloud)

1) Create a new GitHub repo and upload this folder's contents.
2) Go to https://streamlit.io/cloud → **New app** → pick your repo.
   - Main file path: `app/streamlit_app.py`
3) In your deployed app → **⋯ (Settings)** → **Secrets**:
   Paste (replace with your real key):
   ```
   ODDS_API_KEY = "YOUR_ODDS_API_KEY_HERE"
   BOOKS = "fliff,betmgm,draftkings,fanduel,caesars"
   SPORTS = "mlb,wnba,mls"
   PARLAY_MAX_LEGS = "4"
   KELLY_FRACTION = "0.25"
   EDGE_A_THRESHOLD = "2.5"
   EDGE_B_THRESHOLD = "1.0"
   ```
   Click **Save** to redeploy.
4) Open the app, choose sports, and click **Fetch today's slate & build picks**.

## Local Run (optional)
```bash
cp .env.example .env
# edit .env to add your ODDS_API_KEY
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Notes
- v1 uses market no‑vig as fair probability (model = fair). You can add your own model later.
- If you see no picks, odds may not be available yet for that sport or your BOOKS filter is too narrow. Remove BOOKS to broaden.
- Play responsibly. This is for informational/educational use.
