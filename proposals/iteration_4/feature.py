"""Iteration 4 signal: fundamental profitability / earnings-quality.

A truly orthogonal axis to my three prior (price-return) signals, which all
split by sector and were exhausted. This is a slow-moving cross-sectional
QUALITY factor built from universally-reported SEC line items, ranked within
industry to neutralize the sector sign-flips that killed iterations 1-2.
"""
from __future__ import annotations

import sys
import pathlib

import numpy as np
import pandas as pd

# Make the bundled point-in-time fetchers importable.
_SKILL_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "research-methodology" / "scripts"
if str(_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS))

from data import fetch_fundamentals  # noqa: E402


SIGNAL_NAME = "fundamental_quality"
HYPOTHESIS = (
    "High, cash-backed profitability is a persistent quality attribute that a "
    "market fixated on price action and headline earnings underweights, so "
    "firms with high return-on-assets and high cash-flow-on-assets (and low "
    "accruals, i.e. earnings actually backed by cash) are relatively "
    "underpriced and tend to drift up over the next 21 days, while low-quality / "
    "high-accrual firms fade. Ranked within industry to neutralize the "
    "structural profitability differences across Tech/Pharma/Financials."
)

# Universally reported across all three sectors in this universe (incl. banks,
# which do NOT report GrossProfit / OperatingIncomeLoss).
_FLOW_CONCEPTS = {
    "NetIncomeLoss": "ni",
    "NetCashProvidedByUsedInOperatingActivities": "ocf",
}
_STOCK_CONCEPTS = {
    "Assets": "assets",
    "StockholdersEquity": "equity",
}


def _annual_flow_series(fund: pd.DataFrame, concept: str) -> pd.DataFrame:
    """Latest full-fiscal-year (10-K) value of a duration concept, per filed_date.

    Using the annual figure keeps the flow unambiguous (one clean 12-month
    number) and point-in-time (stamped by filed_date). It refreshes once a year
    at the 10-K, which is appropriate for a slow quality factor.
    """
    sub = fund[fund["concept"] == concept].copy()
    if sub.empty:
        return pd.DataFrame(columns=["ticker", "filed_date", "value"])
    sub["period_start"] = pd.to_datetime(sub["period_start"], errors="coerce")
    sub["period_end"] = pd.to_datetime(sub["period_end"], errors="coerce")
    dur = (sub["period_end"] - sub["period_start"]).dt.days
    # Full fiscal year (allow 52/53-week calendars).
    sub = sub[(dur >= 350) & (dur <= 385)].copy()
    sub["filed_date"] = pd.to_datetime(sub["filed_date"], errors="coerce")
    sub = sub.dropna(subset=["filed_date", "value"])
    return sub[["ticker", "filed_date", "value"]]


def _instant_series(fund: pd.DataFrame, concept: str) -> pd.DataFrame:
    """Latest reported value of an instant (balance-sheet) concept, per filed_date."""
    sub = fund[fund["concept"] == concept].copy()
    if sub.empty:
        return pd.DataFrame(columns=["ticker", "filed_date", "value"])
    sub["filed_date"] = pd.to_datetime(sub["filed_date"], errors="coerce")
    sub = sub.dropna(subset=["filed_date", "value"])
    return sub[["ticker", "filed_date", "value"]]


def _asof_merge(panel: pd.DataFrame, series: pd.DataFrame, col: str) -> pd.Series:
    """Point-in-time backward merge: for each panel row take the most recently
    FILED value of `series` with filed_date <= row date, within the same ticker."""
    if series.empty:
        return pd.Series(np.nan, index=panel.index)
    # Collapse duplicate filed_dates (e.g. restatements filed same day) -> keep last.
    s = (
        series.sort_values(["ticker", "filed_date"])
        .drop_duplicates(["ticker", "filed_date"], keep="last")
        .reset_index(drop=True)
    )
    out = pd.Series(np.nan, index=panel.index, dtype="float64")
    for tk, grp in panel.groupby("ticker", sort=False):
        s_tk = s[s["ticker"] == tk]
        if s_tk.empty:
            continue
        left = grp[["date"]].copy()
        left["date"] = left["date"].astype("datetime64[ns]")
        left = left.sort_values("date")
        right = s_tk[["filed_date", "value"]].rename(columns={"filed_date": "date"}).copy()
        right["date"] = right["date"].astype("datetime64[ns]")
        merged = pd.merge_asof(
            left,
            right.sort_values("date"),
            on="date",
            direction="backward",
        )
        out.loc[left.index] = merged["value"].to_numpy()
    return out.rename(col)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    tickers = sorted(panel["ticker"].unique().tolist())
    start = (panel["date"].min() - pd.Timedelta(days=1000)).strftime("%Y-%m-%d")
    end = panel["date"].max().strftime("%Y-%m-%d")

    concepts = list(_FLOW_CONCEPTS) + list(_STOCK_CONCEPTS)
    fund = fetch_fundamentals(tickers, concepts=concepts, start_date=start, end_date=end)

    # Point-in-time levels aligned to each panel row.
    ni = _asof_merge(panel, _annual_flow_series(fund, "NetIncomeLoss"), "ni")
    ocf = _asof_merge(panel, _annual_flow_series(fund, "NetCashProvidedByUsedInOperatingActivities"), "ocf")
    assets = _asof_merge(panel, _instant_series(fund, "Assets"), "assets")
    equity = _asof_merge(panel, _instant_series(fund, "StockholdersEquity"), "equity")

    # Guard denominators (avoid divide-by-tiny/negative equity blowups).
    assets = assets.where(assets > 0)
    equity_safe = equity.where(equity > 0)

    # --- raw fundamental-quality ratios (point-in-time) ---
    panel["q_roa"] = (ni / assets).astype("float64")               # profitability
    panel["q_cfoa"] = (ocf / assets).astype("float64")             # cash-based profitability
    panel["q_accruals"] = ((ni - ocf) / assets).astype("float64")  # Sloan accruals (low = better)
    panel["q_roe"] = (ni / equity_safe).astype("float64")          # profitability on equity

    # --- industry-relative cross-sectional ranks (neutralize sector level) ---
    # Higher rank = higher quality. For accruals, invert (low accruals = quality).
    def _ind_rank(col, ascending=True):
        r = panel.groupby(["date", "industry"])[col].rank(pct=True, ascending=ascending)
        return r

    panel["q_roa_ind"] = _ind_rank("q_roa", ascending=True)
    panel["q_cfoa_ind"] = _ind_rank("q_cfoa", ascending=True)
    panel["q_accruals_ind"] = _ind_rank("q_accruals", ascending=False)  # invert: low accruals -> high rank

    feature_cols = [
        "q_roa", "q_cfoa", "q_accruals", "q_roe",
        "q_roa_ind", "q_cfoa_ind", "q_accruals_ind",
    ]
    return panel, feature_cols


if __name__ == "__main__":
    p = pd.read_pickle("data_cache/panel.pkl")
    out, cols = add_feature(p)
    print("new columns:", cols)
    for c in cols:
        s = out[c]
        print(f"{c:16s} non-null={s.notna().mean():.3f} "
              f"mean={s.mean():.4f} std={s.std():.4f} "
              f"min={s.min():.4f} max={s.max():.4f}")
