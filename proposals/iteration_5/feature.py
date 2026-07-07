"""Iteration 5 signal: asset-growth / investment factor (capital discipline).

Genuinely orthogonal to my prior four signals (price momentum, PEAD earnings
surprise, low-volatility, profitability-quality): this is a balance-sheet
*investment* signal, not a price-return or profitability signal.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals

SIGNAL_NAME = "asset_growth_investment"
HYPOTHESIS = (
    "Firms that expand their asset base aggressively (capex, acquisitions, "
    "issuance-fueled growth) subsequently underperform, while capital-disciplined "
    "firms that grow assets slowly are underpriced and drift up — the investment/"
    "asset-growth anomaly (Cooper-Gulen-Schill), driven by overinvestment, "
    "empire-building and managers timing markets to fund growth, a mispricing the "
    "market corrects gradually. Low year-over-year asset growth therefore predicts "
    "a higher chance of a positive 21-day return. Ranked within industry because "
    "banks grow assets (deposits/loans) structurally differently from Tech/Pharma."
)


def _pit_asset_growth(tickers):
    """Point-in-time YoY and 2yr asset growth, stamped by SEC filing date."""
    fund = fetch_fundamentals(list(tickers), concepts=["Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "ag_2yr"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])
    fund = fund[fund["value"] > 0]

    records = []
    for ticker, grp in fund.groupby("ticker"):
        # Keep the ORIGINAL (earliest-filed) value per fiscal period_end so a later
        # restatement never leaks backward into an earlier decision date.
        grp = (grp.sort_values("filed_date")
                  .drop_duplicates("period_end", keep="first")
                  .sort_values("period_end")
                  .reset_index(drop=True))
        pe = grp["period_end"].values
        val = grp["value"].astype(float).values
        for i in range(len(grp)):
            cur_pe = grp["period_end"].iloc[i]
            cur_val = val[i]

            def growth(years):
                target = cur_pe - pd.Timedelta(days=365 * years)
                # match the period_end closest to `target` within +/- 45 days
                diffs = np.abs((grp["period_end"] - target).dt.days.values)
                j = diffs.argmin()
                if diffs[j] <= 45 and val[j] > 0:
                    return cur_val / val[j] - 1.0
                return np.nan

            records.append({
                "ticker": ticker,
                # information is public only as of the filing date of the CURRENT
                # quarter's balance sheet (the prior-year value was known earlier)
                "avail_date": grp["filed_date"].iloc[i],
                "ag_yoy": growth(1),
                "ag_2yr": growth(2),
            })
    out = pd.DataFrame(records).dropna(subset=["ag_yoy"], how="all")
    # if multiple filings land on the same avail_date, keep the latest period's
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    growth = _pit_asset_growth(panel["ticker"].unique())
    growth["avail_date"] = pd.to_datetime(growth["avail_date"]).astype("datetime64[ns]")
    panel["date"] = panel["date"].astype("datetime64[ns]")

    # point-in-time merge: for each (ticker, date) take the most recent filing
    # whose filing date is on or before that date.
    growth = growth.sort_values("avail_date")
    parts = []
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        gr = growth[growth["ticker"] == ticker][["avail_date", "ag_yoy", "ag_2yr"]]
        if gr.empty:
            g["ag_yoy"] = np.nan
            g["ag_2yr"] = np.nan
        else:
            g = pd.merge_asof(g, gr, left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # Industry-relative cross-sectional rank (same-date only -> no lookahead).
    # Higher rank = SLOWER asset growth = more capital-disciplined = more bullish.
    panel["ag_yoy_ind_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)
    )

    new_cols = ["ag_yoy", "ag_2yr", "ag_yoy_ind_rank"]
    return panel, new_cols
