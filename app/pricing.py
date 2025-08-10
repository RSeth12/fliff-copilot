from __future__ import annotations
from typing import Tuple

# --- Odds conversions ---
def american_to_decimal(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def decimal_to_american(dec: float) -> int:
    if dec <= 1:
        raise ValueError("Decimal odds must be > 1")
    if dec >= 2:
        return int(round((dec - 1) * 100))
    return int(round(-100 / (dec - 1)))

def american_to_prob(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return (-odds) / ((-odds) + 100.0)

def prob_to_american(p: float) -> int:
    if not (0 < p < 1):
        raise ValueError("Probability must be in (0,1)")
    if p < 0.5:
        return int(round(100 * (1 - p) / p))
    return int(round(-100 * p / (1 - p)))

# --- No-vig fair probability for 2-way markets ---
def no_vig_two_way(p_raw_a: float, p_raw_b: float) -> Tuple[float, float]:
    s = p_raw_a + p_raw_b
    if s <= 0:
        raise ValueError("Sum of raw implied probabilities must be > 0")
    return p_raw_a / s, p_raw_b / s

# --- EV and Kelly ---
def expected_value_per_unit(model_prob: float, dec_odds: float) -> float:
    profit_if_win = dec_odds - 1.0
    loss_if_lose = 1.0
    return model_prob * profit_if_win - (1 - model_prob) * loss_if_lose

def kelly_stake_units(model_prob: float, dec_odds: float, kelly_fraction: float = 0.25, bankroll_units: float = 100.0) -> float:
    b = dec_odds - 1.0
    edge = b * model_prob - (1 - model_prob)
    if b <= 0:
        return 0.0
    k = edge / b
    stake_frac = max(0.0, k) * float(kelly_fraction)
    return round(bankroll_units * stake_frac, 2)

def confidence_from_edge(edge_pct: float, a_threshold: float, b_threshold: float) -> str:
    if edge_pct >= a_threshold:
        return "A"
    if edge_pct >= b_threshold:
        return "B"
    return "C"
