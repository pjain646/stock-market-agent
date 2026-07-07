"""Iteration 16 — duration-scaled macro rate-pressure conditions signal.

Builds on the proven macro conditions timer (iter 13, best primary +0.0209) by
adding the per-industry conditioning my notes kept flagging. The refinement is
NOT a sector sign-flip (the data refutes "banks love rising rates" — forward
return correlates negatively with the 10y yield in ALL three sectors on train:
Tech -0.219, Fin -0.131, Pharma -0.048). What varies by industry is the
MAGNITUDE of rate sensitivity: duration ordering Tech > Financials > Pharma.
So the same-signed rate-pressure headwind is scaled by an industry duration
weight, giving cross-sectional lift (which name to prefer) on top of the
sign-stable market-timing score.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                 "research-methodology", "scripts"))
from data import fetch_macro_series  # noqa: E402

SIGNAL_NAME = "duration_scaled_rate_pressure"
HYPOTHESIS = (
    "High and rising Treasury yields raise discount rates and are a bearish "
    "headwind for this large-cap universe (forward returns correlate negatively "
    "with the 10y yield in all three sectors), but the headwind is proportional "
    "to each sector's cash-flow duration — strongest for long-duration Technology, "
    "milder for Financials, weakest for defensive Pharma. Scaling a sign-stable "
    "bullish macro-conditions score (low/falling yields, steeper curve, elevated "
    "VIX risk premium) by an industry duration weight therefore raises the "
    "probability of a positive 21-day return with cross-sectional differentiation."
)

# Structural cash-flow-duration weights (Tech longest duration -> most rate
# sensitive). Ordering is grounded in the train-window rate betas
# (Tech -0.219, Fin -0.131, Pharma -0.048) and standard duration economics;
# rounded to robust values rather than precisely fit, and set from TRAIN only.
_DURATION_WEIGHT = {"Technology": 1.0, "Financials": 0.55, "Pharma": 0.30}


def _trailing_z(s, min_periods=60):
    """Point-in-time z-score: mean/std from an expanding window up to each date."""
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])

    # --- point-in-time daily macro state (FRED, released same/next day) ---
    macro = fetch_macro_series(
        {"DGS10": "y10", "T10Y2Y": "slope", "VIXCLS": "vix"},
        start_date="2013-06-01",
    )
    w = (macro.pivot_table(index="date", columns="series_name", values="value")
         .sort_index())
    w.index = pd.to_datetime(w.index)
    w = w.ffill()  # carry last known value forward (no lookahead)

    w["y10_trend21"] = w["y10"].diff(21)  # 21-business-day change in the 10y

    w["z_y10"] = _trailing_z(w["y10"])
    w["z_y10_trend"] = _trailing_z(w["y10_trend21"])
    w["z_slope"] = _trailing_z(w["slope"])
    w["z_vix"] = _trailing_z(w["vix"])

    # rate pressure: high when yields are high AND rising -> bearish for all
    w["rate_pressure_z"] = w["z_y10"] + w["z_y10_trend"]

    macro_cols = ["rate_pressure_z", "z_slope", "z_vix"]
    daily = w[macro_cols]

    # merge_asof so any panel date lands on the most recent known macro row
    panel = panel.sort_values("date")
    daily_reset = daily.reset_index().rename(columns={"index": "date"}).sort_values("date")
    # align datetime resolution to avoid merge_asof dtype mismatch
    panel["date"] = panel["date"].astype("datetime64[ns]")
    daily_reset["date"] = daily_reset["date"].astype("datetime64[ns]")
    panel = pd.merge_asof(panel, daily_reset, on="date", direction="backward")

    # --- industry-scaled, sign-stable bullish conditions score ---
    panel["irs_duration_weight"] = panel["industry"].map(_DURATION_WEIGHT).fillna(0.55)
    panel["irs_rate_pressure_z"] = panel["rate_pressure_z"]
    # bearish rate pressure scaled by sector duration -> a bullish (negated) penalty
    panel["irs_rate_penalty"] = -panel["irs_duration_weight"] * panel["rate_pressure_z"]
    panel["irs_curve_z"] = panel["z_slope"]          # steeper curve = easing/growth = bullish
    panel["irs_vix_z"] = panel["z_vix"]              # elevated VIX = risk premium earned = bullish

    panel["irs_conditional_score"] = (
        panel["irs_rate_penalty"] + panel["irs_curve_z"] + panel["irs_vix_z"]
    )

    new_cols = [
        "irs_rate_pressure_z",
        "irs_duration_weight",
        "irs_rate_penalty",
        "irs_curve_z",
        "irs_vix_z",
        "irs_conditional_score",
    ]

    # clean up merge helper columns not in the contract set
    panel = panel.drop(columns=[c for c in macro_cols if c not in new_cols],
                       errors="ignore")
    return panel, new_cols
