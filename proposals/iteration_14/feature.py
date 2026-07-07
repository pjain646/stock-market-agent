"""Iteration 14 — macro-timed capital discipline.

Motivation (from 13 iterations of evidence):
  * Iter 13 (macro_financial_conditions) was my only clean logistic winner (+0.0209,
    IC +0.051, positive in all 3 sectors). But it is a *pure date-level* signal — every
    name on a given date gets the identical score — so it times WHEN the universe rises
    yet cannot say WHICH name to prefer.
  * Iter 5 (asset_growth_investment) was my best *cross-sectional* fundamental
    (GBM +0.061, positive-signed in all 3 sectors): capital-disciplined, slow-asset-growth
    firms outperform empire-builders (Cooper-Gulen-Schill), ranked within industry so the
    bank asset-base distortion is neutralized.

These two axes are orthogonal (a regime timer vs. a slow balance-sheet rank) and were BOTH
sign-stable across the low-rate training era and the 2022-24 hiking cycle — the two most
robust ingredients I have found. This signal fuses them into ONE coherent economic idea:

  The capital-discipline premium is a RISK premium that is earned mainly when financial
  conditions are EASING / risk appetite is recovering (rates falling, curve steepening,
  an elevated VIX subsequently normalizing). In those windows investors reward disciplined
  compounders and punish overinvestors; during tightening/stress windows the cross-sectional
  premium compresses (flight dynamics dominate the level move). So the industry-relative
  discipline tilt should be *gated by the macro-conditions regime*: discipline_tilt x
  bullish_macro_score. The product is a genuinely cross-sectional signal (it differentiates
  names on a date) that is switched on/off by the regime — exactly the WHEN x WHICH
  combination that iter 13's pure timing signal left on the table.

PIT discipline: asset growth is stamped by SEC filing date (merge_asof backward); macro
series are forward-filled onto trading days and lagged one business day (FRED value for
day t publishes the morning of t+1). No use of label / forward_return / split.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals, fetch_macro_series


SIGNAL_NAME = "macro_timed_capital_discipline"
HYPOTHESIS = (
    "The capital-discipline premium (slow-asset-growth firms out-drift empire-builders) is a "
    "risk premium earned mainly when financial conditions are easing and risk appetite is "
    "recovering, and it compresses during tightening/stress. Gating a firm's within-industry "
    "asset-growth discipline rank by a sign-stable bullish-macro-conditions score therefore "
    "yields a cross-sectional signal — which names to prefer — that is switched on by the "
    "regime that decides when the universe rises, raising the probability of a positive 21-day return."
)


# --------------------------------------------------------------------------- #
# Cross-sectional leg: point-in-time asset growth (capital discipline)
# --------------------------------------------------------------------------- #
def _pit_asset_growth(tickers):
    """Point-in-time YoY / 2yr asset growth, stamped by SEC filing date."""
    fund = fetch_fundamentals(list(tickers), concepts=["Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "ag_2yr"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])
    fund = fund[fund["value"] > 0]

    records = []
    for ticker, grp in fund.groupby("ticker"):
        # earliest-filed value per fiscal period_end -> no restatement leaks backward
        grp = (grp.sort_values("filed_date")
                  .drop_duplicates("period_end", keep="first")
                  .sort_values("period_end")
                  .reset_index(drop=True))
        val = grp["value"].astype(float).values
        for i in range(len(grp)):
            cur_pe = grp["period_end"].iloc[i]
            cur_val = val[i]

            def growth(years):
                target = cur_pe - pd.Timedelta(days=365 * years)
                diffs = np.abs((grp["period_end"] - target).dt.days.values)
                j = diffs.argmin()
                if diffs[j] <= 45 and val[j] > 0:
                    return cur_val / val[j] - 1.0
                return np.nan

            records.append({
                "ticker": ticker,
                "avail_date": grp["filed_date"].iloc[i],  # public only as of filing date
                "ag_yoy": growth(1),
                "ag_2yr": growth(2),
            })
    out = pd.DataFrame(records).dropna(subset=["ag_yoy"], how="all")
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


# --------------------------------------------------------------------------- #
# Timing leg: sign-stable macro financial-conditions score (from iter 13)
# --------------------------------------------------------------------------- #
def _pit_macro_series(mac, name, dates):
    s = (mac[mac["series_name"] == name][["date", "value"]]
         .set_index("date")["value"].sort_index())
    s = s.reindex(dates.union(s.index)).sort_index().ffill().reindex(dates)
    return s.shift(1)  # value for day t publishes morning of t+1


def _expanding_z(s, min_periods=252):
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std()
    return (s - mean) / std.replace(0.0, np.nan)


def _macro_conditions_score(dates):
    mac = fetch_macro_series({"DGS10": "y10", "DGS2": "y2", "VIXCLS": "vix"},
                             start_date="2013-06-01")
    y10 = _pit_macro_series(mac, "y10", dates)
    y2 = _pit_macro_series(mac, "y2", dates)
    vix = _pit_macro_series(mac, "vix", dates)
    slope = y10 - y2

    y10_level = y10
    y10_trend21 = y10 - y10.shift(21)
    slope_trend21 = slope - slope.shift(21)
    vix_level = vix

    # sign-aligned so higher = more bullish conditions (rates in negatively;
    # curve steepening and VIX in positively — the signs that held across both regimes)
    z = pd.DataFrame({
        "a": -_expanding_z(y10_level),
        "b": -_expanding_z(y10_trend21),
        "c":  _expanding_z(slope_trend21),
        "d":  _expanding_z(vix_level),
    }, index=dates)
    score = z.mean(axis=1, skipna=True)
    return pd.DataFrame({
        "mfc_y10_level": y10_level,
        "mfc_y10_trend21": y10_trend21,
        "mfc_slope_trend21": slope_trend21,
        "mfc_vix_level": vix_level,
        "mtcd_macro_score": score,
    }, index=dates)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = panel["date"].astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---- cross-sectional discipline leg ----
    growth = _pit_asset_growth(panel["ticker"].unique())
    growth["avail_date"] = pd.to_datetime(growth["avail_date"]).astype("datetime64[ns]")
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

    # Higher rank = SLOWER asset growth = more capital-disciplined (same-date only).
    panel["mtcd_disc_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)
    )
    # centre to [-0.5, +0.5] so the sign of the interaction is meaningful
    panel["mtcd_disc_tilt"] = panel["mtcd_disc_rank"] - 0.5

    # ---- macro timing leg ----
    dates = pd.Index(sorted(panel["date"].unique()))
    macro = _macro_conditions_score(dates)
    panel = panel.merge(macro, left_on="date", right_index=True, how="left")

    # ---- the fusion: discipline tilt GATED by the macro regime ----
    # positive when a disciplined name meets easing conditions, negative when an
    # over-investor meets easing conditions OR a disciplined name meets tightening.
    panel["mtcd_interaction"] = panel["mtcd_disc_tilt"] * panel["mtcd_macro_score"]

    new_cols = [
        "ag_yoy",
        "mtcd_disc_rank",
        "mtcd_macro_score",
        "mfc_y10_level",
        "mfc_y10_trend21",
        "mfc_slope_trend21",
        "mfc_vix_level",
        "mtcd_interaction",
    ]
    return panel, new_cols
