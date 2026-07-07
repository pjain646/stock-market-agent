"""Iteration 15 — broad financial-conditions score with an added credit-spread channel.

Builds on iter 13 (pure macro conditions, best primary score +0.0209) and iter 14's
closing recommendation: add a second orthogonal, sign-stable macro channel — the
corporate credit-risk premium — to see if a *broader* conditions score pushes past the
rate/curve/VIX-only ceiling.
"""

import os
import sys

import numpy as np
import pandas as pd

# Make the bundled point-in-time fetchers importable.
_SCRIPTS = os.path.join(
    os.path.dirname(__file__), "..", "..", ".claude", "skills",
    "research-methodology", "scripts",
)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from data import fetch_macro_series  # noqa: E402


SIGNAL_NAME = "credit_broadened_financial_conditions"

HYPOTHESIS = (
    "The 21-day forward direction of this large-cap universe is governed by financial "
    "conditions and risk premia. Iter 13 showed a rate/curve/VIX conditions score times "
    "the market; the corporate credit-risk premium (Moody's Baa/Aaa yield over 10y "
    "Treasury) is an orthogonal, sign-stable channel: a wide credit spread is compensation "
    "for corporate risk that is subsequently earned by equities, so an elevated spread — "
    "added to low/falling yields, a steepening curve and elevated VIX — raises a broadened "
    "bullish-conditions score and the probability of a positive 21-day return."
)

# FRED series -> friendly names.
_SERIES = {
    "DGS10": "y10",       # 10y Treasury yield (discount rate; high = headwind)
    "T10Y2Y": "slope",    # 10y-2y curve (steepening = easing/recovery = tailwind)
    "VIXCLS": "vix",      # equity-implied vol (risk premium subsequently earned)
    "BAA10Y": "baa",      # Moody's Baa corporate spread over 10y (credit-risk premium)
    "AAA10Y": "aaa",      # Moody's Aaa (high-grade) spread over 10y (funding/credit)
}


def _expanding_z(s):
    """Point-in-time z-score: only past+current obs feed the mean/std (no lookahead)."""
    mu = s.expanding(min_periods=20).mean()
    sd = s.expanding(min_periods=20).std()
    z = (s - mu) / sd.replace(0.0, np.nan)
    return z.fillna(0.0)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")

    # --- Pull macro series (disk-cached) and build a daily wide frame. ---
    macro = fetch_macro_series(_SERIES, start_date="2013-01-01")
    wide = (
        macro.pivot(index="date", columns="series_name", values="value")
        .sort_index()
        .ffill()
    )

    # Trends (21 trading-day change ~ 1 month of daily obs).
    wide["y10_trend21"] = wide["y10"] - wide["y10"].shift(21)
    wide["slope_trend21"] = wide["slope"] - wide["slope"].shift(21)
    wide["baa_trend21"] = wide["baa"] - wide["baa"].shift(21)
    wide = wide.ffill()

    # Sign-aligned expanding z-scores for the broad bullish-conditions composite.
    # Signs fixed from economics and confirmed on TRAIN only (never validation/holdout):
    #   low/falling yields (-), steepening curve (+), elevated VIX (+),
    #   wide Baa & Aaa credit spreads (+, risk premium to be earned).
    z_y10 = -_expanding_z(wide["y10"])
    z_y10_tr = -_expanding_z(wide["y10_trend21"])
    z_slope_tr = _expanding_z(wide["slope_trend21"])
    z_vix = _expanding_z(wide["vix"])
    z_baa = _expanding_z(wide["baa"])
    z_aaa = _expanding_z(wide["aaa"])
    wide["conditions_score"] = (
        z_y10 + z_y10_tr + z_slope_tr + z_vix + z_baa + z_aaa
    )

    keep = [
        "y10", "y10_trend21", "slope_trend21", "vix",
        "baa", "aaa", "baa_trend21", "conditions_score",
    ]
    wide = wide.reset_index()[["date"] + keep]
    wide["date"] = wide["date"].astype("datetime64[ns]")

    # --- Point-in-time as-of merge: use the latest macro obs on/<= each panel date. ---
    dates = pd.DataFrame(
        {"date": pd.to_datetime(sorted(panel["date"].unique()))}
    ).astype("datetime64[ns]")
    merged = pd.merge_asof(dates, wide.sort_values("date"), on="date")

    rename = {
        "y10": "fcc_y10_level",
        "y10_trend21": "fcc_y10_trend21",
        "slope_trend21": "fcc_slope_trend21",
        "vix": "fcc_vix_level",
        "baa": "fcc_baa_level",
        "aaa": "fcc_aaa_level",
        "baa_trend21": "fcc_baa_trend21",
        "conditions_score": "fcc_conditions_score",
    }
    merged = merged.rename(columns=rename)
    feature_cols = list(rename.values())

    panel = panel.merge(merged, on="date", how="left")
    # Any pre-history gaps: fill forward then with column median (macro is date-level).
    for c in feature_cols:
        panel[c] = panel[c].ffill()
        panel[c] = panel[c].fillna(panel[c].median())

    return panel, feature_cols
