from __future__ import annotations
from typing import Any, Dict, List, Tuple
from .pricing import american_to_prob, american_to_decimal, no_vig_two_way, expected_value_per_unit, kelly_stake_units, confidence_from_edge

def _best_prices_two_way(bookmakers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for bm in bookmakers:
        book_key = bm.get("key")
        for market in bm.get("markets", []):
            if market.get("key") not in ("h2h", "spreads", "totals"):
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name")
                price = outcome.get("price")
                sel_key = f"{market.get('key')}::{name}"
                if sel_key not in best or price > best[sel_key]["price"]:
                    best[sel_key] = {"price": price, "book": book_key, "point": outcome.get("point")}
    return best

def two_way_fair_probs(bookmakers: List[Dict[str, Any]], market_key: str, side_a: str, side_b: str) -> Tuple[float, float]:
    raw_a, raw_b, n = 0.0, 0.0, 0
    for bm in bookmakers:
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            outcomes = {o["name"]: o for o in m.get("outcomes", [])}
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

def build_straight_picks(event: Dict[str, Any], kelly_fraction: float, bankroll_units: float, edge_A: float, edge_B: float) -> List[Dict[str, Any]]:
    picks: List[Dict[str, Any]] = []
    bms = event.get("bookmakers", [])

    fair_home, fair_away = two_way_fair_probs(bms, "h2h", event.get("home_team"), event.get("away_team"))
    best = _best_prices_two_way(bms)

    for sel_key, info in best.items():
        market_key, name = sel_key.split("::", 1)
        if market_key != "h2h":
            continue
        price = info["price"]
        dec = american_to_decimal(price)
        if name == event.get("home_team"):
            fair = fair_home
        elif name == event.get("away_team"):
            fair = fair_away
        else:
            continue
        if fair <= 0 or fair >= 1:
            continue
        model = fair  # v1 market-anchored
        edge = (model - fair) * 100.0  # 0 in v1; placeholder for v2 model blend
        ev = expected_value_per_unit(model, dec)
        stake = kelly_stake_units(model, dec, kelly_fraction, bankroll_units)
        conf = confidence_from_edge(edge, edge_A, edge_B)
        picks.append({
            "event_id": event.get("id"),
            "sport_key": event.get("sport_key"),
            "commence_time": event.get("commence_time"),
            "market": "moneyline",
            "selection": name,
            "book": info["book"],
            "odds": price,
            "decimal": dec,
            "fair_prob": round(fair, 4),
            "model_prob": round(model, 4),
            "edge_pct": round(edge, 2),
            "ev_per_unit": round(ev, 4),
            "stake_units": stake,
            "confidence": conf,
            "reason": f"Market-anchored fair prob {round(fair*100,2)}% at best price {price} ({info['book']})."
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
