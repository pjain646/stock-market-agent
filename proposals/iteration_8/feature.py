"""Iteration 8 signal: profitability acceleration (fundamental momentum in ROA).

Genuinely orthogonal to my prior signals. Iteration 4 tested profitability
*levels* (ROA/CFOA/accruals); this tests the *change/trend* in profitability —
a distinct anomaly (Novy-Marx-style fundamental momentum). It is NOT a
price/catalyst-continuation signal (momentum, PEAD both reversed in this
universe); it is a slow-moving balance-sheet/income signal, the family that
carried the only real (tree) edge in iterations 4/5/7.

Built on NetIncomeLoss + Assets because those are the only fundamental concepts
with clean coverage across all three sectors (Tech/Pharma/Financials) — revenue
and operating-income tags are sparse for banks, so a margin-based trend would
silently drop Financials. ROA generalizes to banks.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals

SIGNAL_NAME = "profitability_acceleration"
HYPOTHESIS = (
    "The market underreacts to inflections in operating profitability: a firm "
    "whose trailing return-on-assets is improving year-over-year is on a "
    "strengthening fundamental trajectory that prices in only gradually "
    "(fundamental momentum). A rising ROA therefore predicts a higher chance of "
    "a positive 21-day return, while deteriorating profitability fades. Uses the "
    "CHANGE in ROA (orthogonal to the ROA level), and is ranked within industry "
    "to neutralize the structural profitability gap between banks and Tech/Pharma."
)


def _nearest(period_ends, values, target, tol_days=50):
    """Return value whose period_end is closest to `target` within tol_days, else nan."""
    diffs = np.abs((pd.to_datetime(pd.Series(list(period_ends))) - target).dt.days.values)
    j = int(np.argmin(diffs))
    if diffs[j] <= tol_days:
        return values[j], j
    return np.nan, -1


def _pit_roa_trend(tickers):
    """Point-in-time annual ROA and its YoY / 2yr change, stamped by SEC filing date."""
    fund = fetch_fundamentals(list(tickers),
                              concepts=["NetIncomeLoss", "Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "pm_roa",
                                     "pm_roa_chg", "pm_roa_chg_2y"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    # --- Annual net income: duration concept, ~365-day windows only ---
    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 350) & (ni["dur"] <= 385)]
    # earliest-filed value per fiscal period -> no restatement leaks backward
    # (dedup WITHIN ticker: different tickers can share a fiscal period_end)
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first")
            .sort_values("period_end"))

    # --- Assets: instant concept (no period_start) ---
    assets = fund[fund["concept"] == "Assets"].copy()
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first")
                    .sort_values("period_end"))

    records = []
    for ticker in ni["ticker"].unique():
        ni_t = ni[ni["ticker"] == ticker].reset_index(drop=True)
        as_t = assets[assets["ticker"] == ticker].reset_index(drop=True)
        if ni_t.empty or as_t.empty:
            continue
        as_pe = as_t["period_end"]
        as_val = as_t["value"].astype(float).values

        # Build annual ROA series keyed by fiscal period_end.
        pe_list, roa_list, filed_list = [], [], []
        for i in range(len(ni_t)):
            cur_pe = ni_t["period_end"].iloc[i]
            ni_val = float(ni_t["value"].iloc[i])
            a_val, j = _nearest(as_pe, as_val, cur_pe, tol_days=50)
            if not np.isfinite(a_val) or a_val <= 0:
                continue
            pe_list.append(cur_pe)
            roa_list.append(ni_val / a_val)
            # info public only once BOTH the income and balance sheet are filed
            filed_list.append(max(ni_t["filed_date"].iloc[i],
                                  as_t["filed_date"].iloc[j]))

        if not pe_list:
            continue
        pe_arr = pd.to_datetime(pd.Series(pe_list))
        roa_arr = np.array(roa_list, dtype=float)

        for i in range(len(pe_arr)):
            cur_pe = pe_arr.iloc[i]

            def chg(years):
                target = cur_pe - pd.Timedelta(days=365 * years)
                diffs = np.abs((pe_arr - target).dt.days.values)
                k = int(np.argmin(diffs))
                if diffs[k] <= 60 and k != i:
                    return roa_arr[i] - roa_arr[k]
                return np.nan

            records.append({
                "ticker": ticker,
                "avail_date": filed_list[i],
                "pm_roa": roa_arr[i],
                "pm_roa_chg": chg(1),
                "pm_roa_chg_2y": chg(2),
            })

    out = pd.DataFrame(records)
    if out.empty:
        return out
    out = out.dropna(subset=["pm_roa_chg"], how="all")
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    trend = _pit_roa_trend(panel["ticker"].unique())
    if trend.empty:
        for c in ["pm_roa", "pm_roa_chg", "pm_roa_chg_2y", "pm_roa_chg_ind_rank"]:
            panel[c] = np.nan
        return panel, ["pm_roa", "pm_roa_chg", "pm_roa_chg_2y", "pm_roa_chg_ind_rank"]

    trend["avail_date"] = pd.to_datetime(trend["avail_date"]).astype("datetime64[ns]")
    trend = trend.sort_values("avail_date")

    parts = []
    cols = ["pm_roa", "pm_roa_chg", "pm_roa_chg_2y"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        tr = trend[trend["ticker"] == ticker][["avail_date"] + cols]
        if tr.empty:
            for c in cols:
                g[c] = np.nan
        else:
            g = pd.merge_asof(g, tr, left_on="date", right_on="avail_date",
                              direction="backward")
            g = g.drop(columns=["avail_date"])
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # Industry-relative rank of the YoY ROA change on each date (same-date only,
    # no lookahead). Higher change = improving profitability = more bullish, so
    # ascending=True puts the strongest improvers near rank 1.0.
    panel["pm_roa_chg_ind_rank"] = (
        panel.groupby(["date", "industry"])["pm_roa_chg"]
        .rank(pct=True, ascending=True)
    )

    new_cols = ["pm_roa", "pm_roa_chg", "pm_roa_chg_2y", "pm_roa_chg_ind_rank"]
    return panel, new_cols
