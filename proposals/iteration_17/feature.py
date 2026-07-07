"""Iteration 17 — rate-beta-scaled macro rate pressure.

Refines iteration 16 (duration_scaled_rate_pressure, the best signal so far,
+0.0521 logistic uplift) by replacing the coarse 3-level *industry* duration
weight with a CONTINUOUS, point-in-time, per-name rate sensitivity estimated
from each stock's own price history.
"""

import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                 "research-methodology", "scripts"))
from data import fetch_macro_series  # noqa: E402

SIGNAL_NAME = "rate_beta_scaled_rate_pressure"
HYPOTHESIS = (
    "High and rising Treasury yields raise discount rates and are a bearish "
    "headwind for this large-cap universe, and the headwind is proportional to "
    "each firm's realized cash-flow duration -- which its own price reveals "
    "through how strongly its returns co-move with 10y-yield changes. Scaling a "
    "sign-stable bullish macro-conditions score (low/falling yields, a steepening "
    "curve, an elevated VIX risk premium) by a continuous, point-in-time per-name "
    "rate-sensitivity MAGNITUDE (sign fixed, so it cannot flip) sharpens the "
    "cross-sectional differentiation of iteration 16's coarse industry duration "
    "buckets and raises the probability of a positive 21-day return."
)

# --- parameters ---
_BETA_WINDOW = 120       # trailing trading days for the rolling rate-beta
_BETA_MINP = 60          # min observations before a beta is defined
_MACRO_TREND = 21        # days for the yield/curve momentum
_EXP_MINP = 252          # min obs before an expanding macro z-score is trusted


def _expanding_z(s):
    """Point-in-time standardization: mean/std use only data up to each date."""
    mean = s.expanding(min_periods=_EXP_MINP).mean()
    std = s.expanding(min_periods=_EXP_MINP).std()
    z = (s - mean) / std
    return z.replace([np.inf, -np.inf], np.nan)


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")

    # ---------------------------------------------------------------
    # 1) Macro series (FRED), forward-filled onto calendar, PIT z-scores.
    # ---------------------------------------------------------------
    start = (panel["date"].min() - pd.Timedelta(days=800)).strftime("%Y-%m-%d")
    macro = fetch_macro_series({"DGS10": "y10", "T10Y2Y": "curve",
                                "VIXCLS": "vix"}, start_date=start)
    macro["date"] = pd.to_datetime(macro["date"])
    mp = (macro.pivot(index="date", columns="series_name", values="value")
          .sort_index().ffill())

    # daily change in the 10y yield (the risk factor for the rate-beta)
    mp["d_y10"] = mp["y10"].diff()

    # Sign-stable bullish-conditions components (all higher == more bullish):
    #  - low / falling 10y yield  -> use -level, -trend
    #  - steepening curve         -> +trend of the 10y-2y slope
    #  - elevated VIX             -> +level (forward risk premium earned)
    y10_trend = mp["y10"] - mp["y10"].shift(_MACRO_TREND)
    curve_trend = mp["curve"] - mp["curve"].shift(_MACRO_TREND)

    # rate PRESSURE: high == bearish (this is what gets scaled by duration)
    mp["rate_pressure_z"] = (_expanding_z(mp["y10"]) + _expanding_z(y10_trend)) / 2.0
    mp["curve_z"] = _expanding_z(curve_trend)
    mp["vix_z"] = _expanding_z(mp["vix"])

    macro_cols = ["d_y10", "rate_pressure_z", "curve_z", "vix_z"]
    mp_daily = mp[macro_cols].reset_index()
    mp_daily["date"] = mp_daily["date"].astype("datetime64[ns]")

    # Merge macro onto each panel row by date (as-of forward fill for gaps).
    panel = panel.sort_values("date")
    panel = pd.merge_asof(panel, mp_daily, on="date", direction="backward")

    # ---------------------------------------------------------------
    # 2) Per-name rolling rate-sensitivity (magnitude only), point-in-time.
    #    beta_t = trailing cov(stock_ret, d_y10) / var(d_y10) over 120 days,
    #    using only data up to and including the current row.
    # ---------------------------------------------------------------
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel["ret"] = panel.groupby("ticker")["adj_close"].pct_change()

    g = panel.groupby("ticker")

    def _roll_mean(col):
        return g[col].transform(
            lambda x: x.rolling(_BETA_WINDOW, min_periods=_BETA_MINP).mean())

    panel["_rd"] = panel["ret"] * panel["d_y10"]
    panel["_dd"] = panel["d_y10"] * panel["d_y10"]

    m_r = _roll_mean("ret")
    m_d = _roll_mean("d_y10")
    m_rd = _roll_mean("_rd")
    m_dd = _roll_mean("_dd")

    cov = m_rd - m_r * m_d
    var = m_dd - m_d * m_d
    beta = cov / var.replace(0, np.nan)

    # duration proxy = MAGNITUDE of rate sensitivity (sign fixed -> can't flip)
    panel["rate_sensitivity"] = beta.abs()

    # ---------------------------------------------------------------
    # 3) Continuous, split-immune duration weight: relative to the
    #    cross-sectional mean sensitivity on each date (dimensionless, ~1).
    # ---------------------------------------------------------------
    xs_mean = panel.groupby("date")["rate_sensitivity"].transform("mean")
    panel["duration_weight"] = panel["rate_sensitivity"] / xs_mean.replace(0, np.nan)
    # clip extreme relative weights so a single volatile print can't dominate
    panel["duration_weight"] = panel["duration_weight"].clip(0.2, 3.0)

    # ---------------------------------------------------------------
    # 4) Conditional score: bearish rate pressure scaled by per-name
    #    duration, plus the two undirected bullish macro channels.
    # ---------------------------------------------------------------
    panel["rate_penalty"] = -panel["rate_pressure_z"] * panel["duration_weight"]
    panel["rbs_conditional_score"] = (
        panel["rate_penalty"] + panel["curve_z"] + panel["vix_z"])

    feature_cols = [
        "rate_pressure_z",
        "rate_sensitivity",
        "duration_weight",
        "rate_penalty",
        "curve_z",
        "vix_z",
        "rbs_conditional_score",
    ]

    panel = panel.drop(columns=["ret", "d_y10", "_rd", "_dd"])
    return panel, feature_cols
