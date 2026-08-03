"""Dashboard-only monetary framing of a signal's out-of-sample predictions.

NOT used anywhere in the research loop. core/evaluator.py's tested_score
(PR-AUC uplift) remains the only thing a feature is ever ranked, selected, or
gated on — this module never feeds back into that decision. It exists purely
to turn the same out-of-sample rows into the one number a non-technical
dashboard viewer can act on: money.
"""
from __future__ import annotations

import pandas as pd


def top5_vs_universe(
    scored_rows: pd.DataFrame,
    starting_balance: float = 500.0,
    top_n: int = 5,
    period_trading_days: int = 21,
    date_column: str = "date",
    ticker_column: str = "ticker",
    score_column: str = "predicted_up_probability",
    return_column: str = "forward_return",
) -> dict:
    """Simulate picking the top-N stocks every `period_trading_days` and
    holding for that period, versus spreading the same money evenly across
    every stock the model was choosing from that period.

    Periods are non-overlapping so a single price move never gets counted
    twice: trading days are taken in order and a new period starts every
    `period_trading_days`-th one. On each period's start date, every stock
    already carries a `forward_return` looking exactly `period_trading_days`
    days ahead (how labels are built — see core/labeling.py), so picking a
    stock on that date already IS the return from holding it the whole
    period; no daily re-ranking is needed or performed.

    Returns a dict with both compounded balances, a per-period breakdown (for
    a chart), and the final dollar/percent edge. {"error": ...} if there
    isn't enough data for at least two periods.
    """
    usable = scored_rows.dropna(subset=[date_column, score_column, return_column])
    if usable.empty:
        return {"error": "no scored rows with predictions and forward returns"}

    trading_dates = sorted(usable[date_column].unique())
    period_start_dates = trading_dates[::period_trading_days]
    if len(period_start_dates) < 2:
        return {"error": "fewer than 2 non-overlapping periods available"}

    top5_balance = starting_balance
    universe_balance = starting_balance
    periods = []
    for period_start in period_start_dates:
        day_rows = usable[usable[date_column] == period_start]
        if day_rows.empty:
            continue
        ranked = day_rows.sort_values(score_column, ascending=False)
        top_picks = ranked.head(top_n)

        top5_return = float(top_picks[return_column].mean())
        universe_return = float(day_rows[return_column].mean())

        top5_balance *= (1.0 + top5_return)
        universe_balance *= (1.0 + universe_return)

        periods.append({
            "period_start": str(period_start)[:10],
            "n_eligible": int(len(day_rows)),
            "top5_tickers": ", ".join(top_picks[ticker_column].astype(str).tolist())
                            if ticker_column in top_picks.columns else "",
            "top5_return": round(top5_return, 4),
            "universe_return": round(universe_return, 4),
            "top5_balance": round(top5_balance, 2),
            "universe_balance": round(universe_balance, 2),
        })

    if not periods:
        return {"error": "no periods had eligible rows"}

    return {
        "starting_balance": starting_balance,
        "top_n": top_n,
        "period_trading_days": period_trading_days,
        "n_periods": len(periods),
        "first_period": periods[0]["period_start"],
        "last_period": periods[-1]["period_start"],
        "top5_final_balance": round(top5_balance, 2),
        "universe_final_balance": round(universe_balance, 2),
        "dollar_edge": round(top5_balance - universe_balance, 2),
        "pct_edge": round((top5_balance / universe_balance - 1.0) * 100, 2) if universe_balance else None,
        "periods": periods,
    }
