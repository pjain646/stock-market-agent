"""Iteration 11 signal: earnings (ROA) stability — the fundamental "safety" leg.

Every prior iteration mined the LEVEL, TREND, or GROWTH of fundamentals. This one
mines their DISPERSION: how volatile a firm's return-on-assets has been over the
past several years. Built on NetIncome/Assets, the only two XBRL concepts reported
by every name in the panel (banks included), so it stays comparable across sectors.
"""

import os
import sys

import numpy as np
import pandas as pd

# Make the bundled point-in-time fetchers importable.
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "research-methodology",
    "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from data import fetch_fundamentals  # noqa: E402

SIGNAL_NAME = "earnings_stability"
HYPOTHESIS = (
    "Firms with steady, low-volatility return-on-assets are lower fundamental-risk "
    "'quality-safety' names (the QMJ safety leg); the market underweights boring "
    "consistency and over-discounts erratic earners, so stable-earnings firms are "
    "relatively underpriced and drift up over the next 21 days while volatile earners "
    "keep disappointing. Built on ROA (NetIncome/Assets) so it is well-defined for "
    "leveraged banks and should hold a monotone sign across all three sectors."
)

# Trailing annual-ROA window used to measure stability.
_MAX_YEARS = 5
_MIN_YEARS = 3


def _annual_roa_events(tickers):
    """Return, per ticker, a filed_date-stamped stream of trailing ROA-stability stats.

    Point-in-time safe: each fiscal year's ROA becomes available only on the
    filed_date of its ORIGINAL 10-K, and trailing statistics at any event use only
    fiscal years disclosed on or before that event.
    """
    fund = fetch_fundamentals(tickers, concepts=["NetIncomeLoss", "Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "filed_date", "roa_std", "roa_ir", "stability"])

    fund["filed_date"] = pd.to_datetime(fund["filed_date"])
    fund["period_end"] = pd.to_datetime(fund["period_end"])
    fund["period_start"] = pd.to_datetime(fund["period_start"])

    # --- Annual net income: full-year duration reported on an annual filing. ---
    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni[ni["form"].isin(["10-K", "10-K/A"])]
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 340) & (ni["dur"] <= 380)]
    # Original as-filed value for each fiscal-year-end (avoid restatement lookahead).
    ni = (
        ni.sort_values("filed_date")
        .groupby(["ticker", "period_end"], as_index=False)
        .first()[["ticker", "period_end", "filed_date", "value"]]
        .rename(columns={"filed_date": "ni_filed", "value": "net_income"})
    )

    # --- Total assets: instant concept at each balance-sheet date. ---
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = (
        assets.sort_values("filed_date")
        .groupby(["ticker", "period_end"], as_index=False)
        .first()[["ticker", "period_end", "filed_date", "value"]]
        .rename(columns={"filed_date": "assets_filed", "value": "assets"})
    )

    roa = ni.merge(assets, on=["ticker", "period_end"], how="inner")
    roa = roa[(roa["assets"].notna()) & (roa["assets"] > 0)]
    roa["roa"] = roa["net_income"] / roa["assets"]
    # The fiscal-year figure is public only once BOTH numbers are filed.
    roa["avail"] = roa[["ni_filed", "assets_filed"]].max(axis=1)
    roa = roa.sort_values(["ticker", "period_end"])

    events = []
    for ticker, grp in roa.groupby("ticker"):
        grp = grp.sort_values("period_end")
        roas = grp["roa"].tolist()
        avails = grp["avail"].tolist()
        for i in range(len(grp)):
            window = roas[max(0, i - _MAX_YEARS + 1): i + 1]
            if len(window) < _MIN_YEARS:
                continue
            arr = np.asarray(window, dtype=float)
            std = float(np.std(arr, ddof=1))
            mean = float(np.mean(arr))
            ir = mean / std if std > 1e-9 else np.nan
            events.append(
                {
                    "ticker": ticker,
                    # Available the day AFTER filing (first fully actionable open).
                    "filed_date": avails[i] + pd.Timedelta(days=1),
                    "roa_std": std,
                    "roa_ir": ir,
                    "stability": -std,  # higher = more stable = bullish
                }
            )

    return pd.DataFrame(events).sort_values(["ticker", "filed_date"]).reset_index(drop=True)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")

    tickers = sorted(panel["ticker"].unique())
    events = _annual_roa_events(tickers)
    if not events.empty:
        events["filed_date"] = events["filed_date"].astype("datetime64[ns]")

    new_cols = ["es_roa_std", "es_roa_ir", "es_stability", "es_stability_ind_rank"]
    for c in new_cols:
        panel[c] = np.nan

    if events.empty:
        return panel, new_cols

    # Point-in-time asof-merge: attach the most recent stability stats known on `date`.
    out = []
    for ticker, grp in panel.groupby("ticker", sort=False):
        ev = events[events["ticker"] == ticker]
        grp = grp.sort_values("date")
        if ev.empty:
            out.append(grp)
            continue
        merged = pd.merge_asof(
            grp,
            ev[["filed_date", "roa_std", "roa_ir", "stability"]].sort_values("filed_date"),
            left_on="date",
            right_on="filed_date",
            direction="backward",
        )
        merged["es_roa_std"] = merged["roa_std"].values
        merged["es_roa_ir"] = merged["roa_ir"].values
        merged["es_stability"] = merged["stability"].values
        merged = merged.drop(columns=["filed_date", "roa_std", "roa_ir", "stability"])
        merged.index = grp.index
        out.append(merged)

    panel = pd.concat(out).sort_index()

    # Industry-relative rank (per date) of stability: neutralises structural
    # cross-sector earnings-volatility differences (banks vs pharma vs tech).
    def _rank(s):
        return s.rank(pct=True)

    panel["es_stability_ind_rank"] = (
        panel.groupby(["date", "industry"])["es_stability"].transform(_rank)
    )

    return panel, new_cols
