from __future__ import annotations
from typing import Any, Dict, List, Tuple
from pricing import (
    american_to_prob,
    american_to_decimal,
    no_vig_two_way,
    expected_value_per_unit,
    kelly_stake_units,
    confidence_from_edge,
)

# ---------- helpers ----------

def _aliases(home: str, away: str) -> Dict[str, str]:
    # map "home"/"away" and team names to canonical team names
    return {
        "home": home,
        "away": away,
        home: home,
        away: away,
    }

def _best_prices_two_way(bookmakers: List[Dict[str, Any]], allowed_books: List[str] | None = None) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for bm in bookmakers:
        book_key = bm.get("key")
        if allowed_books and book_key not in allowed_books:
            continue
        for market in bm.get("markets", []):
            if market.get("key") not in ("h2h", "spreads", "totals"):
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name")
                price = outcome.get("price")
                sel_key = f"{market.get('key')}::{name}"
                if name is None or price is None:
                    continue
                if sel_key not in best or price > best[sel_key]["price"]:
                    best[sel_key] = {"price": price, "book": book_key, "point": outcome.get("point")}
    return best

def _collect_two_way_by_point(bookmakers, market_key, side_a, side_b):
    """Return dict: {point: (sum_raw_prob_a, sum_raw_prob_b, count)} across books."""
    buckets = {}
    alias = _aliases(side_a, side_b)
    for bm in bookmakers:
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            outs = m.get("outcomes", [])
            pts = {}
            for o in outs:
                name = o.get("name")
                pt = o.get("point")
                price = o.get("price")
                if name is None or pt is None or price is None:
                    continue
                # normalize side to team name when possible
                norm = alias.get(name, name)
                if norm in (side_a, side_b):
                    pts.setdefault(pt, {})[norm] = price
            for pt, d in pts.items():
                if side_a in d and side_b in d:
                    pa = american_to_prob(d[side_a])
                    pb = american_to_prob(d[side_b])
                    a, b, n = buckets.get(pt, (0.0, 0.0, 0))
                    buckets[pt] = (a + pa, b + pb, n + 1)
    return buckets

def _best_prices_two_way_with_point(bookmakers, market_key, allowed_books=None, side_alias=None):
    """Return best price per (selection, point). selection is canonical team or 'Over'/'Under'."""
    best = {}
    for bm in bookmakers:
        book_key = bm.get("key")
        if allowed_books and book_key not in allowed_books:
            continue
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            for o in m.get("outcomes", []):
                name = o.get("name")
                pt = o.get("point")
                price = o.get("price")
                if name is None or pt is None or price is None:
                    continue
                if side_alias:
                    name = side_alias.get(name, name)
                key = (name, float(pt))
                if key not in best or price > best[key]["price"]:
                    best[key] = {"price": price, "book": book_key, "point": float(pt)}
    return best

# ---------- builders ----------

def build_straight_picks(event: Dict[str, Any], kelly_fraction: float, bankroll_units: float,
                         edge_A: float, edge_B: float, price_books: List[str] | None = None) -> List[Dict[str, Any]]:
    picks: List[Dict[str, Any]] = []
    bms = event.get("bookmakers", [])
    fair_home, fair_away = two_way_fair_probs(bms, "h2h", event.get("home_team"), event.get("away_team"))
    best = _best_prices_two_way(bms, allowed_books=price_books)

    for sel_key, info in best.items():
        market_key, name = sel_key.split("::", 1)
        if market_key != "h2h":
            continue
        price = info["price"]
        dec = american_to_decimal(price)
        if name in ("home", event.get("home_team")):
            fair = fair_home
            sel_name = event.get("home_team")
        elif name in ("away", event.get("away_team")):
            fair = fair_away
            sel_name = event.get("away_team")
        else:
            continue
        if not (0 < fair < 1):
            continue
        model = fair
        edge = (model - fair) * 100.0
        ev = expected_value_per_unit(model, dec)
        stake = kelly_stake_units(model, dec, kelly_fraction, bankroll_units)
        picks.append({
            "event_id": event.get("id"),
            "sport_key": event.get("sport_key"),
            "commence_time": event.get("commence_time"),
            "market": "moneyline",
            "selection": sel_name,
            "book": info["book"],
            "odds": price,
            "decimal": dec,
            "fair_prob": round(fair, 4),
            "model_prob": round(model, 4),
            "edge_pct": round(edge, 2),
            "ev_per_unit": round(ev, 4),
            "stake_units": stake,
            "confidence": confidence_from_edge(edge, edge_A, edge_B),
            "reason": f"Market-anchored fair prob at best price {price} ({info['book']})."
        })
    return sorted(picks, key=lambda x: (-x["ev_per_unit"], -x["stake_units"]))

def two_way_fair_probs(bookmakers: List[Dict[str, Any]], market_key: str, side_a: str, side_b: str) -> Tuple[float, float]:
    raw_a, raw_b, n = 0.0, 0.0, 0
    alias = _aliases(side_a, side_b)
    for bm in bookmakers:
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            outcomes = {}
            for o in m.get("outcomes", []):
                nm = o.get("name")
                if nm is None:
                    continue
                nm = alias.get(nm, nm)
                outcomes[nm] = o
            if side_a in outcomes and side_b in outcomes:
                pa = american_to_prob(outcomes[side_a]["price"])
                pb = american_to_prob(outcomes[side_b]["price"])
                raw_a += pa
                raw_b += pb
                n += 1
    if n == 0:
        return 0.0, 0.0
    pa, pb = raw_a / n, raw_b / n
    return no_vig_two_way(pa, pb)

def build_spread_picks(event, kelly_fraction, bankroll_units, edge_A, edge_B, price_books=None):
    picks = []
    bms = event.get("bookmakers", [])
    home, away = event.get("home_team"), event.get("away_team")
    alias = _aliases(home, away)

    buckets = _collect_two_way_by_point(bms, "spreads", home, away)
    best = _best_prices_two_way_with_point(bms, "spreads", allowed_books=price_books, side_alias=alias)

    for pt, (sum_a, sum_b, n) in buckets.items():
        if n == 0:
            continue
        pa_raw, pb_raw = sum_a / n, sum_b / n
        pa, pb = no_vig_two_way(pa_raw, pb_raw)
        for name, fair in ((home, pa), (away, pb)):
            key = (name, float(pt))
            if key not in best:
                continue
            info = best[key]
            dec = american_to_decimal(info["price"])
            model = fair
            edge = (model - fair) * 100.0
            ev = expected_value_per_unit(model, dec)
            stake = kelly_stake_units(model, dec, kelly_fraction, bankroll_units)
            picks.append({
                "event_id": event.get("id"),
                "sport_key": event.get("sport_key"),
                "commence_time": event.get("commence_time"),
                "market": f"spread {pt:+}",
                "selection": f"{name} {pt:+}",
                "book": info["book"],
                "odds": info["price"],
                "decimal": dec,
                "fair_prob": round(fair, 4),
                "model_prob": round(model, 4),
                "edge_pct": round(edge, 2),
                "ev_per_unit": round(ev, 4),
                "stake_units": stake,
                "confidence": confidence_from_edge(edge, edge_A, edge_B),
                "reason": f"Consensus fair at {pt:+} using full market; priced with {info['book']}."
            })
    return sorted(picks, key=lambda x: (-x["ev_per_unit"], -x["stake_units"]))

def build_total_picks(event, kelly_fraction, bankroll_units, edge_A, edge_B, price_books=None):
    picks = []
    bms = event.get("bookmakers", [])
    buckets = _collect_two_way_by_point(bms, "totals", "Over", "Under")
    best = _best_prices_two_way_with_point(bms, "totals", allowed_books=price_books)

    for pt, (sum_o, sum_u, n) in buckets.items():
        if n == 0:
            continue
        po_raw, pu_raw = sum_o / n, sum_u / n
        po, pu = no_vig_two_way(po_raw, pu_raw)
        for name, fair in (("Over", po), ("Under", pu)):
            key = (name, float(pt))
            if key not in best:
                continue
            info = best[key]
            dec = american_to_decimal(info["price"])
            model = fair
            edge = (model - fair) * 100.0
            ev = expected_value_per_unit(model, dec)
            stake = kelly_stake_units(model, dec, kelly_fraction, bankroll_units)
            picks.append({
                "event_id": event.get("id"),
                "sport_key": event.get("sport_key"),
                "commence_time": event.get("commence_time"),
                "market": f"total {pt}",
                "selection": f"{name} {pt}",
                "book": info["book"],
                "odds": info["price"],
                "decimal": dec,
                "fair_prob": round(fair, 4),
                "model_prob": round(model, 4),
                "edge_pct": round(edge, 2),
                "ev_per_unit": round(ev, 4),
                "stake_units": stake,
                "confidence": confidence_from_edge(edge, edge_A, edge_B),
                "reason": f"Consensus fair O/U {pt}; priced with {info['book']}."
            })
    return sorted(picks, key=lambda x: (-x["ev_per_unit"], -x["stake_units"]))

def build_prop_picks(event, prop_market_keys, kelly_fraction, bankroll_units, edge_A, edge_B, price_books=None):
    picks = []
    bms = event.get("bookmakers", [])
    for mkey in prop_market_keys:
        buckets = _collect_two_way_by_point(bms, mkey, "Over", "Under")
        best = _best_prices_two_way_with_point(bms, mkey, allowed_books=price_books)
        for pt, (sum_o, sum_u, n) in buckets.items():
            if n == 0:
                continue
            po_raw, pu_raw = sum_o / n, sum_u / n
            po, pu = no_vig_two_way(po_raw, pu_raw)
            for name, fair in (("Over", po), ("Under", pu)):
                key = (name, float(pt))
                if key not in best:
                    continue
                info = best[key]
                dec = american_to_decimal(info["price"])
                model = fair
                edge = (model - fair) * 100.0
                ev = expected_value_per_unit(model, dec)
                stake = kelly_stake_units(model, dec, kelly_fraction, bankroll_units)
                picks.append({
                    "event_id": event.get("id"),
                    "sport_key": event.get("sport_key"),
                    "commence_time": event.get("commence_time"),
                    "market": f"{mkey} {pt}",
                    "selection": f"{name} {pt}",
                    "book": info["book"],
                    "odds": info["price"],
                    "decimal": dec,
                    "fair_prob": round(fair, 4),
                    "model_prob": round(model, 4),
                    "edge_pct": round(edge, 2),
                    "ev_per_unit": round(ev, 4),
                    "stake_units": stake,
                    "confidence": confidence_from_edge(edge, edge_A, edge_B),
                    "reason": f"Consensus fair for {mkey} @ {pt}; priced with {info['book']}."
                })
    return sorted(picks, key=lambda x: (-x["ev_per_unit"], -x["stake_units"]))

def build_parlays(picks: List[Dict[str, Any]], conservative_legs: int = 2, balanced_legs: int = 3, fun_max_legs: int = 4) -> List[Dict[str, Any]]:
    by_event = {}
    for p in picks:
        by_event.setdefault(p["event_id"], []).append(p)
    per_event_best = [sorted(v, key=lambda x: -x["ev_per_unit"])[0] for v in by_event.values()]
    per_event_best = sorted(per_event_best, key=lambda x: -x["ev_per_unit"])[:12]

    def _combine(legs: List[Dict[str, Any]]):
        prob = 1.0
        price = 1.0
        for l in legs:
            prob *= l["model_prob"]
            price *= l["decimal"]
        ev = prob * (price - 1) - (1 - prob)
        return prob, price, ev

    outputs = []
    buckets = [("Conservative 2-leg", conservative_legs), ("Balanced 3-leg", balanced_legs), ("Fun", min(fun_max_legs, max(2, len(per_event_best) // 3)))]
    for name, n_legs in buckets:
        legs = per_event_best[:n_legs]
        if len(legs) < n_legs:
            continue
        prob, price, ev = _combine(legs)
        outputs.append({
            "name": name,
            "legs": [{"event_id": l["event_id"], "selection": l["selection"], "odds": l["odds"], "book": l["book"]} for l in legs],
            "combined_decimal": round(price, 4),
            "est_hit_prob": round(prob, 4),
            "est_ev": round(ev, 4),
            "notes": "Assumes independence; avoid same-game legs for v1."
        })
    return outputs

def find_near_misses(picks: List[Dict[str, Any]], ev_floor: float = -0.02, ev_ceiling: float = 0.0, limit: int = 10) -> List[Dict[str, Any]]:
    near = [p for p in picks if ev_floor <= p["ev_per_unit"] < ev_ceiling]
    near.sort(key=lambda x: -x["ev_per_unit"])
    return near[:limit]
