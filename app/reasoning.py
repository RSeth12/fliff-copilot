def explain_pick(pick: dict) -> str:
    return (
        f"{pick['selection']} moneyline at {pick['odds']} on {pick['book']}: "
        f"Fair={round(pick['fair_prob']*100,1)}%, Model={round(pick['model_prob']*100,1)}%, "
        f"EV={round(pick['ev_per_unit'],3)} per unit. "
        f"{pick['reason']}"
    )
