"""Feature pipeline — turn raw data into model inputs, always point-in-time.

The honest judge scores *features*. This file builds them from the fetched data
(prices, earnings, insider trades), and the cardinal rule throughout is: for any
given ticker on any given date, a feature may only use information that was
already public on that date. No peeking at the future.

How that's enforced:
  - Price features (momentum, volatility) only look backward by construction.
  - Earnings & insider features are merged in "as of" the date they became public
    (the earnings report date / the Form 4 filing date), using a backward-looking
    join — so a feature on Jan 10 never reflects an earnings report from Jan 20.

Each `add_*` function takes the panel and returns it with new feature columns,
so you can compose just the ones you have data for.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Form 4 transaction codes that represent real open-market conviction trades.
INSIDER_BUY_CODE = "P"   # open-market purchase (bullish)
INSIDER_SELL_CODE = "S"  # open-market sale

# Balance-sheet ("instant") concepts describe a single point in time, so there's
# no quarterly-vs-cumulative ambiguity — only the restatement one.
INSTANT_FUNDAMENTAL_CONCEPTS = {
    "Assets", "Liabilities", "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue", "LongTermDebtNoncurrent",
}
# The two revenue tags companies use; whichever one a filer reports, coalesce
# into a single `revenue` column.
_REVENUE_CONCEPTS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]


def add_technical_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Price-based features: momentum over several horizons + recent volatility.

    These only use past prices, so they're point-in-time by construction.
    """
    feature_frames = []
    for _ticker, single_ticker_history in panel.sort_values("date").groupby("ticker", sort=False):
        single_ticker_history = single_ticker_history.copy()
        daily_return = single_ticker_history["adj_close"].pct_change()
        single_ticker_history["momentum_21d"] = single_ticker_history["adj_close"].pct_change(21)
        single_ticker_history["momentum_63d"] = single_ticker_history["adj_close"].pct_change(63)
        single_ticker_history["momentum_252d"] = single_ticker_history["adj_close"].pct_change(252)
        single_ticker_history["volatility_21d"] = daily_return.rolling(21).std()
        feature_frames.append(single_ticker_history)
    return pd.concat(feature_frames).reset_index(drop=True)


def add_earnings_features(panel: pd.DataFrame, earnings: pd.DataFrame) -> pd.DataFrame:
    """Earnings-based features, merged in as of each earnings *report* date.

    Adds: last_eps_surprise, eps_surprise_avg_4q (consistency of beats),
    revenue_growth_yoy, eps_growth_yoy, and days_since_earnings.
    """
    # Build a per-report-date table of earnings features (only realized earnings).
    earnings_feature_rows = []
    realized = earnings[earnings["eps_actual"].notna()].sort_values("date")
    for _ticker, single_ticker_earnings in realized.groupby("ticker", sort=False):
        single_ticker_earnings = single_ticker_earnings.copy()
        single_ticker_earnings["eps_surprise_avg_4q"] = single_ticker_earnings["eps_surprise"].rolling(4).mean()
        # Year-over-year growth: 4 quarters back.
        single_ticker_earnings["revenue_growth_yoy"] = single_ticker_earnings["revenue_actual"].pct_change(4)
        single_ticker_earnings["eps_growth_yoy"] = single_ticker_earnings["eps_actual"].pct_change(4)
        earnings_feature_rows.append(single_ticker_earnings)

    earnings_features = pd.concat(earnings_feature_rows)
    earnings_features = earnings_features.rename(
        columns={"date": "earnings_report_date", "eps_surprise": "last_eps_surprise"}
    )
    # The join key is the report date (when the numbers became public).
    earnings_features["date"] = earnings_features["earnings_report_date"]
    earnings_features = earnings_features[[
        "ticker", "date", "earnings_report_date",
        "last_eps_surprise", "eps_surprise_avg_4q", "revenue_growth_yoy", "eps_growth_yoy",
    ]].sort_values("date")

    # As-of join: each panel row gets the most recent earnings known on/before its date.
    panel_with_earnings = pd.merge_asof(
        panel.sort_values("date"),
        earnings_features,
        on="date", by="ticker", direction="backward",
    )
    panel_with_earnings["days_since_earnings"] = (
        panel_with_earnings["date"] - panel_with_earnings["earnings_report_date"]
    ).dt.days
    return panel_with_earnings.reset_index(drop=True)


def add_insider_features(panel: pd.DataFrame, insider_transactions: pd.DataFrame,
                         window_days: int = 90) -> pd.DataFrame:
    """Insider trading pressure: net shares bought minus sold over a trailing window.

    Positive = insiders net buying (a bullish conviction signal); negative = net
    selling. Everything is dated by the Form 4 *filing date* (when it went public),
    so it's point-in-time.
    """
    relevant_trades = insider_transactions[
        insider_transactions["transaction_code"].isin([INSIDER_BUY_CODE, INSIDER_SELL_CODE])
    ].dropna(subset=["shares", "filing_date"]).copy()

    # Sign each trade: buys add, sells subtract.
    relevant_trades["signed_shares"] = np.where(
        relevant_trades["transaction_code"] == INSIDER_BUY_CODE,
        relevant_trades["shares"], -relevant_trades["shares"],
    )

    insider_feature_frames = []
    for ticker, single_ticker_panel in panel.groupby("ticker", sort=False):
        ticker_trades = relevant_trades[relevant_trades["ticker"] == ticker]
        # Default feature = 0 (no insider activity) when we have no data for the name.
        if ticker_trades.empty:
            block = single_ticker_panel.copy()
            block["insider_net_shares_90d"] = 0.0
            insider_feature_frames.append(block)
            continue

        # Net signed shares per filing day, then a calendar-day rolling window sum.
        daily_net_shares = (
            ticker_trades.groupby("filing_date")["signed_shares"].sum().sort_index()
        )
        full_day_range = pd.date_range(
            daily_net_shares.index.min(), single_ticker_panel["date"].max(), freq="D"
        )
        daily_net_shares = daily_net_shares.reindex(full_day_range, fill_value=0.0)
        trailing_window_net = daily_net_shares.rolling(f"{window_days}D").sum()

        block = single_ticker_panel.copy()
        block["insider_net_shares_90d"] = (
            block["date"].map(trailing_window_net).fillna(0.0).values
        )
        insider_feature_frames.append(block)

    return pd.concat(insider_feature_frames).reset_index(drop=True)


def _clean_fundamentals_to_one_row_per_period(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Collapse SEC's raw XBRL facts to one honest value per (ticker, concept, period_end).

    Two problems solved here, both flagged as open issues in earlier sessions:
      - Duration concepts (revenue, income, cash flow) get reported more than once
        under the same `period_end` — a single quarter AND a cumulative
        year-to-date total share the same end date. Keep only single-quarter rows
        (`period_end - period_start` in [75, 100] days) so quarter-over-quarter
        growth compares like with like. Instant concepts (Assets, etc.) have no
        `period_start` and aren't affected.
      - Restatements: a period can be refiled later (e.g. a 10-K/A) with a revised
        number. Keeping the row with the EARLIEST `filed_date` per period is what
        was actually public at the time — using a later restatement would leak
        hindsight backward into a point-in-time feature.
    """
    working = fundamentals.copy()
    is_instant = working["concept"].isin(INSTANT_FUNDAMENTAL_CONCEPTS)
    quarter_length_days = (working["period_end"] - working["period_start"]).dt.days
    is_single_quarter = quarter_length_days.between(75, 100)
    working = working[is_instant | is_single_quarter]

    return (
        working.sort_values("filed_date")
        .drop_duplicates(subset=["ticker", "concept", "period_end"], keep="first")
    )


def add_fundamental_features(panel: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Financial-statement-based features, merged in as of each filing's `filed_date`.

    Adds margins (gross/operating/net), leverage (long-term debt to equity),
    cash-flow quality (operating cash flow vs. reported net income), point-in-time
    trailing P/E, and quarter-over-quarter growth (revenue, net income) — all
    stamped by the date the underlying filing became public, so a feature on any
    given date only reflects what was actually known then.
    """
    clean = _clean_fundamentals_to_one_row_per_period(fundamentals)

    # Every concept in the same filing became public on the same day; collapse
    # to one filed_date per (ticker, period_end) before pivoting.
    filed_date_per_period = clean.groupby(["ticker", "period_end"])["filed_date"].max()
    wide = clean.pivot_table(
        index=["ticker", "period_end"], columns="concept", values="value", aggfunc="first"
    )
    wide = wide.join(filed_date_per_period).reset_index()

    revenue_columns = [c for c in _REVENUE_CONCEPTS if c in wide.columns]
    if revenue_columns:
        wide["revenue"] = wide[revenue_columns[0]]
        for column in revenue_columns[1:]:  # fill gaps from the next-preferred tag
            wide["revenue"] = wide["revenue"].combine_first(wide[column])
    else:
        wide["revenue"] = np.nan

    def _column_or_nan(frame: pd.DataFrame, column_name: str) -> pd.Series:
        # Not every filer reports every tag (e.g. banks don't report GrossProfit) —
        # fall back to an all-NaN series so the ratio math below degrades to NaN
        # instead of crashing on `None / Series`.
        if column_name in frame.columns:
            return frame[column_name]
        return pd.Series(np.nan, index=frame.index)

    fundamental_feature_frames = []
    for _ticker, single_ticker_fundamentals in wide.sort_values("period_end").groupby("ticker", sort=False):
        single_ticker_fundamentals = single_ticker_fundamentals.copy()
        revenue = _column_or_nan(single_ticker_fundamentals, "revenue")
        net_income = _column_or_nan(single_ticker_fundamentals, "NetIncomeLoss")

        single_ticker_fundamentals["gross_margin"] = _column_or_nan(single_ticker_fundamentals, "GrossProfit") / revenue
        single_ticker_fundamentals["operating_margin"] = (
            _column_or_nan(single_ticker_fundamentals, "OperatingIncomeLoss") / revenue
        )
        single_ticker_fundamentals["net_margin"] = net_income / revenue
        single_ticker_fundamentals["debt_to_equity"] = (
            _column_or_nan(single_ticker_fundamentals, "LongTermDebtNoncurrent")
            / _column_or_nan(single_ticker_fundamentals, "StockholdersEquity")
        )
        single_ticker_fundamentals["cash_to_assets"] = (
            _column_or_nan(single_ticker_fundamentals, "CashAndCashEquivalentsAtCarryingValue")
            / _column_or_nan(single_ticker_fundamentals, "Assets")
        )
        # Earnings quality: operating cash flow relative to reported net income.
        # Well above 1 = income is backed by real cash; well below 1 = a flag.
        single_ticker_fundamentals["ocf_to_net_income"] = (
            _column_or_nan(single_ticker_fundamentals, "NetCashProvidedByUsedInOperatingActivities") / net_income
        )
        single_ticker_fundamentals["revenue_growth_yoy_fundamental"] = revenue.pct_change(4, fill_method=None)
        single_ticker_fundamentals["net_income_growth_yoy_fundamental"] = net_income.pct_change(4, fill_method=None)
        # Trailing-twelve-month diluted EPS, for a point-in-time P/E ratio.
        eps_diluted = _column_or_nan(single_ticker_fundamentals, "EarningsPerShareDiluted")
        single_ticker_fundamentals["eps_diluted_ttm"] = eps_diluted.rolling(4).sum()
        fundamental_feature_frames.append(single_ticker_fundamentals)

    fundamental_features = pd.concat(fundamental_feature_frames)
    fundamental_features = fundamental_features.rename(columns={"period_end": "fundamentals_period_end"})
    fundamental_features["date"] = fundamental_features["filed_date"]
    fundamental_features = fundamental_features[[
        "ticker", "date", "fundamentals_period_end",
        "gross_margin", "operating_margin", "net_margin", "debt_to_equity", "cash_to_assets",
        "ocf_to_net_income", "revenue_growth_yoy_fundamental", "net_income_growth_yoy_fundamental",
        "eps_diluted_ttm",
    ]].sort_values("date")

    # As-of join: each panel row gets the most recent filing known on/before its date.
    panel_with_fundamentals = pd.merge_asof(
        panel.sort_values("date"),
        fundamental_features,
        on="date", by="ticker", direction="backward",
    )
    # Point-in-time P/E: today's price over the most recently known trailing EPS.
    # Negative/zero trailing earnings makes P/E meaningless, so leave those as NaN.
    trailing_eps = panel_with_fundamentals["eps_diluted_ttm"]
    panel_with_fundamentals["pe_ratio"] = np.where(
        trailing_eps > 0, panel_with_fundamentals["adj_close"] / trailing_eps, np.nan
    )
    return panel_with_fundamentals.reset_index(drop=True)


def build_feature_panel(panel: pd.DataFrame, earnings: pd.DataFrame | None = None,
                        insider_transactions: pd.DataFrame | None = None,
                        fundamentals: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compose the full point-in-time feature panel from whatever data we have.

    Always adds technical features; adds earnings, insider, and fundamental
    features when those DataFrames are provided. Returns the panel with all
    feature columns attached.
    """
    feature_panel = add_technical_features(panel)
    if earnings is not None and not earnings.empty:
        feature_panel = add_earnings_features(feature_panel, earnings)
    if insider_transactions is not None and not insider_transactions.empty:
        feature_panel = add_insider_features(feature_panel, insider_transactions)
    if fundamentals is not None and not fundamentals.empty:
        feature_panel = add_fundamental_features(feature_panel, fundamentals)
    return feature_panel
