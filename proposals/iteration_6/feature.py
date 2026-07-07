"""Iteration 6 — Net payout / shareholder-yield (capital-return discipline).

Economic axis: how much cash a firm returns to shareholders (buybacks + dividends,
net of new equity issuance) relative to its asset base. This is the mirror image of
iteration-5's asset-growth signal: disciplined capital allocators that shrink their
share count and return cash tend to be under-priced and drift up, while capital-
raising / diluting firms (net issuers) subsequently underperform (the net-issuance /
net-payout anomaly; Boudoukh-Michaely-Richardson-Roberts, Daniel-Titman,
Pontiff-Woodgate). All inputs are dollar-denominated cash-flow-statement flows, so
the signal is immune to the stock-split contamination that corrupts raw XBRL share
counts. Ranked within industry because banks return capital under regulatory
constraints on a huge asset base, structurally unlike Tech/Pharma.
"""

import sys
import pathlib

import numpy as np
import pandas as pd

_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / ".claude" / "skills" / "research-methodology" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from data import fetch_fundamentals  # noqa: E402

SIGNAL_NAME = "net_payout_yield"
HYPOTHESIS = (
    "Firms that return more cash to shareholders — buybacks plus dividends net of new "
    "equity issuance, relative to their asset base — are capital-disciplined and tend to "
    "be under-priced, drifting up over the next 21 days, while net issuers/diluters "
    "underperform (net-payout / net-issuance anomaly). Dollar-denominated so it is "
    "split-immune, and ranked within industry to neutralize the structural payout "
    "differences between capital-constrained banks and Tech/Pharma."
)

# Cash-flow (duration) concepts are annualized by 365/duration so quarterly and
# year-to-date filings collapse to a consistent annual rate; Assets is an instant.
_REPURCHASE = "PaymentsForRepurchaseOfCommonStock"
_ISSUANCE = "ProceedsFromIssuanceOfCommonStock"
_DIV = "PaymentsOfDividends"
_DIV_COMMON = "PaymentsOfDividendsCommonStock"
_ASSETS = "Assets"

_FLOW_CONCEPTS = [_REPURCHASE, _ISSUANCE, _DIV, _DIV_COMMON]
_ALL_CONCEPTS = _FLOW_CONCEPTS + [_ASSETS]


def _annualized_flow_series(fund, ticker, concept):
    """Point-in-time series of an annualized $ flow for one ticker/concept.

    Returns a frame [filed_date, val] sorted by filed_date, one row per filing
    (latest filing wins at merge_asof time, which respects restatements)."""
    s = fund[(fund["ticker"] == ticker) & (fund["concept"] == concept)].copy()
    if s.empty:
        return None
    dur = (s["period_end"] - s["period_start"]).dt.days
    s = s[dur.between(80, 400)].copy()
    if s.empty:
        return None
    dur = (s["period_end"] - s["period_start"]).dt.days
    s["ann"] = s["value"].astype(float) * 365.0 / dur
    s = s.sort_values("filed_date")[["filed_date", "ann"]]
    return s.rename(columns={"ann": "val"}).reset_index(drop=True)


def _instant_series(fund, ticker, concept):
    s = fund[(fund["ticker"] == ticker) & (fund["concept"] == concept)].copy()
    if s.empty:
        return None
    s = s.sort_values("filed_date")[["filed_date", "value"]]
    return s.rename(columns={"value": "val"}).reset_index(drop=True)


def _asof_merge(panel_t, series):
    """merge_asof (backward) a per-ticker series onto panel dates. NaN where no
    filing was public yet as of the row date."""
    if series is None or series.empty:
        return pd.Series(np.nan, index=panel_t.index)
    left = panel_t[["date"]].copy()
    left["date"] = left["date"].astype("datetime64[ns]")
    series = series.copy()
    series["filed_date"] = series["filed_date"].astype("datetime64[ns]")
    merged = pd.merge_asof(
        left.sort_values("date"),
        series.sort_values("filed_date"),
        left_on="date",
        right_on="filed_date",
        direction="backward",
    )
    merged.index = panel_t.sort_values("date").index
    return merged["val"].reindex(panel_t.index)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    tickers = sorted(panel["ticker"].unique())
    start = (panel["date"].min() - pd.Timedelta(days=900)).strftime("%Y-%m-%d")
    end = panel["date"].max().strftime("%Y-%m-%d")
    fund = fetch_fundamentals(tickers, concepts=_ALL_CONCEPTS, start_date=start, end_date=end)

    for col in ["repurch_ann", "issuance_ann", "div_ann", "div_common_ann", "assets_pit"]:
        panel[col] = np.nan

    for tkr in tickers:
        mask = panel["ticker"] == tkr
        pt = panel.loc[mask]
        panel.loc[mask, "repurch_ann"] = _asof_merge(pt, _annualized_flow_series(fund, tkr, _REPURCHASE))
        panel.loc[mask, "issuance_ann"] = _asof_merge(pt, _annualized_flow_series(fund, tkr, _ISSUANCE))
        panel.loc[mask, "div_ann"] = _asof_merge(pt, _annualized_flow_series(fund, tkr, _DIV))
        panel.loc[mask, "div_common_ann"] = _asof_merge(pt, _annualized_flow_series(fund, tkr, _DIV_COMMON))
        panel.loc[mask, "assets_pit"] = _asof_merge(pt, _instant_series(fund, tkr, _ASSETS))

    # Coalesce dividend tags; treat missing repurchase/issuance/dividends as 0 flow
    # (a firm that reports no buyback line simply didn't repurchase materially).
    div = panel["div_ann"].fillna(panel["div_common_ann"]).fillna(0.0)
    repurch = panel["repurch_ann"].fillna(0.0)
    issuance = panel["issuance_ann"].fillna(0.0)

    assets = panel["assets_pit"].where(panel["assets_pit"] > 0)

    net_payout = repurch + div - issuance          # $ returned to shareholders, net
    net_issuance = issuance - repurch              # net equity issued ($); the bearish side

    panel["npy_net_payout_to_assets"] = (net_payout / assets).clip(-0.5, 0.5)
    panel["npy_buyback_to_assets"] = (repurch / assets).clip(0.0, 0.5)
    panel["npy_net_issuance_to_assets"] = (net_issuance / assets).clip(-0.5, 0.5)

    # Where we never saw any payout filing AND no assets, the row is genuinely unknown.
    unknown = panel["assets_pit"].isna()
    for c in ["npy_net_payout_to_assets", "npy_buyback_to_assets", "npy_net_issuance_to_assets"]:
        panel.loc[unknown, c] = np.nan

    # Industry-relative rank of the primary signal (per date), neutralizing the
    # structural bank/non-bank payout-level gap. 0.5 for solo/ties.
    panel["npy_net_payout_ind_rank"] = (
        panel.groupby(["date", "industry"])["npy_net_payout_to_assets"]
        .rank(pct=True)
        .fillna(0.5)
    )

    feature_cols = [
        "npy_net_payout_to_assets",
        "npy_buyback_to_assets",
        "npy_net_issuance_to_assets",
        "npy_net_payout_ind_rank",
    ]

    panel = panel.drop(columns=["repurch_ann", "issuance_ann", "div_ann", "div_common_ann", "assets_pit"])
    return panel, feature_cols
