"""Retrospective grading — did the model's past top-10 picks actually pan out?

Reads `candidates/picks_history.csv` (each day's top-10 snapshot, appended by
`core.candidates.log_picks_snapshot` — see `research_pipeline.py`'s
`rank_stock_candidates`) and, once a cohort is old enough that its
`config.LABEL_HORIZON`-trading-day window has actually elapsed, grades it
against realized prices from `candidates/price_cache.parquet` (the same cache
`build_live_panel()` uses — already covers every UNIVERSE ticker's full
history, so no extra fetch needed for the picks themselves).

The model only ever claims RELATIVE outperformance ("expected to rise the
most"), never a guaranteed absolute rise — see the header dashboard copy — so
every cohort is graded against a benchmark (SPY) as the primary measure, with
plain absolute up/down kept as a secondary number. A pick that fell 3% while
the market fell 8% is a genuine hit on the model's own terms, not a miss.

Never invents a result for a cohort that hasn't matured yet: the dashboard's
job is to show a countdown until then, not fake an early answer.
"""
from __future__ import annotations

import pathlib

import pandas as pd


def load_picks_history(history_path: pathlib.Path) -> pd.DataFrame:
    """Every top-10 snapshot ever logged, oldest first. Empty (not missing)
    if the pipeline hasn't logged anything yet."""
    if not history_path.exists():
        return pd.DataFrame(columns=["date", "ticker", "industry", "rank",
                                     "predicted_up_probability"])
    history = pd.read_csv(history_path)
    history["date"] = pd.to_datetime(history["date"])
    return history.sort_values(["date", "rank"]).reset_index(drop=True)


def _trading_calendar(price_panel: pd.DataFrame) -> pd.DatetimeIndex:
    """The real trading calendar, taken from actual fetched prices rather
    than a weekday approximation (which would miss market holidays and
    throw the exact 21-trading-day offset off by a day or two)."""
    return pd.DatetimeIndex(sorted(price_panel["date"].unique()))


def _price_lookup(price_panel: pd.DataFrame) -> dict:
    """{(ticker, date) -> adj_close}, for O(1) lookups while grading many
    (ticker, cohort-date) pairs."""
    return {(row.ticker, row.date): row.adj_close
            for row in price_panel.itertuples(index=False)}


def grade_cohort(cohort: pd.DataFrame, trading_calendar: pd.DatetimeIndex,
                 price_lookup: dict, benchmark_lookup: dict,
                 label_horizon_days: int = 21) -> dict | None:
    """Grade ONE day's top-10 snapshot. Returns None if the horizon hasn't
    actually elapsed yet on the real trading calendar (not just calendar
    days) — a cohort logged 25 calendar days ago might still be short of
    21 TRADING days depending on holidays/weekends.
    """
    pick_date = cohort["date"].iloc[0]
    on_or_after = trading_calendar[trading_calendar >= pick_date]
    if len(on_or_after) <= label_horizon_days:
        return None  # not enough trading days have elapsed since this pick
    entry_date = on_or_after[0]
    exit_date = on_or_after[label_horizon_days]

    benchmark_entry = benchmark_lookup.get(entry_date)
    benchmark_exit = benchmark_lookup.get(exit_date)
    if benchmark_entry is None or benchmark_exit is None or benchmark_entry == 0:
        return None  # benchmark data gap — don't grade with a broken baseline
    benchmark_return = (benchmark_exit / benchmark_entry) - 1.0

    graded_picks = []
    for row in cohort.itertuples():
        entry_price = price_lookup.get((row.ticker, entry_date))
        exit_price = price_lookup.get((row.ticker, exit_date))
        if entry_price is None or exit_price is None or entry_price == 0:
            continue  # a delisting, a data gap — skip this one pick, not the cohort
        stock_return = (exit_price / entry_price) - 1.0
        graded_picks.append({
            "ticker": row.ticker,
            "rank": int(row.rank),
            "stock_return": stock_return,
            "beat_benchmark": stock_return > benchmark_return,
            "up_absolute": stock_return > 0,
        })
    if not graded_picks:
        return None

    n_graded = len(graded_picks)
    n_beat = sum(p["beat_benchmark"] for p in graded_picks)
    n_up = sum(p["up_absolute"] for p in graded_picks)
    return {
        "pick_date": pick_date.strftime("%Y-%m-%d"),
        "graded_date": exit_date.strftime("%Y-%m-%d"),
        "benchmark_return": benchmark_return,
        "n_graded": n_graded,
        "pct_beat_benchmark": n_beat / n_graded,
        "pct_up_absolute": n_up / n_graded,
        "avg_stock_return": sum(p["stock_return"] for p in graded_picks) / n_graded,
        "picks": sorted(graded_picks, key=lambda p: p["rank"]),
    }


def build_retrospective(history_path: pathlib.Path, price_cache_path: pathlib.Path,
                        fetch_benchmark_prices, label_horizon_days: int = 21,
                        benchmark_ticker: str = "SPY") -> dict:
    """Top-level entry point. `fetch_benchmark_prices(ticker, start, end)` is
    injected (rather than imported directly) so this module stays free of
    the research-methodology-skill sys.path dance every other network-facing
    module in core/ already does — callers pass
    `research-methodology/scripts/data.py`'s `fetch_prices`.

    Returns:
      {"graded": [...cohorts, newest first...],
       "pending_trading_days": N or None,
       "n_logged_cohorts": N}
    A cohort not yet 21 trading days old is never included in "graded" —
    it's reflected only in "pending_trading_days" (via the OLDEST
    not-yet-mature cohort, since that one matures soonest).
    """
    history = load_picks_history(history_path)
    if history.empty:
        return {"graded": [], "pending_trading_days": None, "n_logged_cohorts": 0}

    if not price_cache_path.exists():
        return {"graded": [], "pending_trading_days": None,
               "n_logged_cohorts": history["date"].nunique()}
    price_panel = pd.read_parquet(price_cache_path)
    price_panel["date"] = pd.to_datetime(price_panel["date"])
    trading_calendar = _trading_calendar(price_panel)
    price_lookup = _price_lookup(price_panel)

    earliest_pick_date = history["date"].min()
    benchmark_history = fetch_benchmark_prices(
        [benchmark_ticker], earliest_pick_date.date().isoformat(),
        pd.Timestamp.today().date().isoformat())
    benchmark_lookup = ({(row.date): row.adj_close for row in benchmark_history.itertuples(index=False)}
                        if not benchmark_history.empty else {})

    graded = []
    pending_dates = []
    for pick_date, cohort in history.groupby("date"):
        result = grade_cohort(cohort, trading_calendar, price_lookup, benchmark_lookup,
                              label_horizon_days)
        if result is not None:
            graded.append(result)
        else:
            pending_dates.append(pick_date)

    pending_trading_days = None
    if pending_dates:
        # The OLDEST pending cohort matures soonest — that's the one whose
        # countdown the dashboard should show.
        soonest = min(pending_dates)
        elapsed = int((trading_calendar >= soonest).sum())
        pending_trading_days = max(label_horizon_days - elapsed, 0)

    graded.sort(key=lambda c: c["pick_date"], reverse=True)
    return {
        "graded": graded,
        "pending_trading_days": pending_trading_days,
        "n_logged_cohorts": history["date"].nunique(),
    }
