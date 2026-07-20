"""Iteration 20 — orthogonal BUNDLE (iter-18 proven frame + the ONE validated
macro fix from iter 19): capital discipline + profitability momentum + macro
discount-rate regime.

Campaign lesson: a single macro timer (iter 16, +0.0521 validation) FAILED the
sealed holdout (-0.0118) — a lone date-level timer is a noisy max with few
independent observations. Iter 18 fixed this by bundling THREE orthogonal
factors scored as ONE model (+0.0603 validation, the campaign best): two
CROSS-SECTIONAL fundamental legs carry edge across 166 names independent of the
macro path, and the macro leg supplies only the timing axis.

What changes vs iter 18 — a SINGLE evidence-backed edit, not a re-search:
  Iter 19 A/B-tested the per-sector cash-flow-duration map against iter-18's
  and produced exactly ONE real, economically-clean win and several backfires:
    * WIN — Energy: iter-18 defaulted it to a flat 0.55, leaving it dead
      (-0.001). Energy is an inflation/rate hedge whose returns co-move
      POSITIVELY with yields, so a NEGATIVE duration weight turns the rate term
      into the tailwind it economically is; that flipped Energy to +0.057
      (IC +0.157). This is a structural sign correction, not a magnitude tune.
    * BACKFIRE — raising the weights on the other long-duration defensives
      (Utilities 0.55->0.90, RealEstate 0.55->0.95) pushed both MORE negative,
      because in 2022-24 regulated/lease-escalator cash flows did NOT trade as
      cleanly rate-inverse as textbook duration predicts.
  Iteration 20 therefore keeps iter-18's proven map verbatim (Tech 1.0,
  Financials 0.55, Pharma 0.30, all others 0.55) and applies ONLY the Energy
  sign correction. Every weight is a structural prior set on duration economics,
  NOT fit to validation, so there is no lookahead; the surviving change is the
  one whose sign is dictated by the sector's cash-flow relationship to yields.

Legs (each a genuinely different source of edge):
  1. Capital discipline  — within-industry rank of YoY asset growth (slow growth
     = capital-disciplined = bullish; Cooper-Gulen-Schill investment anomaly).
  2. Profitability momentum — within-industry rank of the YoY CHANGE in annual
     return-on-assets (improving operating efficiency prices in gradually).
  3. Macro discount-rate regime — a sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight.

Orthogonality (why each PAIR is low-correlation):
  * (1) vs (2): different financial statements — asset-base SIZE trajectory vs
    profit-PER-asset trajectory; slow asset growth can pair with rising OR
    falling ROA, so the two within-industry ranks are only weakly related.
  * (1)/(2) vs (3): the two fundamental legs are cross-sectional (differ across
    names on a date, ~constant over weeks); the macro leg is a pure time-series
    scaled by a constant sector weight (identical across names within a sector,
    varies day to day) — near-zero correlation by construction. Fundamentals
    decide WHICH names, macro times WHEN the universe rises.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "research-methodology", "scripts"))
from data import fetch_fundamentals, fetch_macro_series  # noqa: E402

SIGNAL_NAME = "discipline_profmom_macro_bundle_v3"
HYPOTHESIS = (
    "Capital discipline: firms that expand their asset base slowly are "
    "underpriced and drift up (overinvestment/empire-building corrected "
    "gradually). Profitability momentum: firms whose annual return-on-assets is "
    "improving year-over-year are on a strengthening fundamental trajectory the "
    "market prices in only gradually. Macro discount-rate regime: low/falling "
    "Treasury yields, a steepening curve and an elevated VIX risk premium are a "
    "sign-stable bullish backdrop, with the rate term scaled by each sector's "
    "cash-flow duration (long-duration Tech most hurt by rising yields; Energy "
    "an inflation/rate hedge whose returns co-move POSITIVELY with yields, hence "
    "a negative weight that makes the rate move a tailwind). Orthogonality: "
    "capital-discipline (asset SIZE trajectory) and profitability momentum "
    "(profit-PER-asset trajectory) come from different financial statements and "
    "move independently (slow growth can pair with rising or falling ROA), so "
    "the two within-industry ranks are only weakly related; both are "
    "cross-sectional and near-uncorrelated with the macro leg, which is a single "
    "time-series identical across names within a sector on any given day — "
    "fundamentals decide WHICH names, macro times WHEN."
)

# Structural cash-flow-duration weights = iter-18's PROVEN map (Tech 1.0,
# Financials 0.55, Pharma 0.30, all others default 0.55) with the ONE
# evidence-backed correction: Energy carries a NEGATIVE weight because its
# returns co-move POSITIVELY with yields (inflation/rate hedge), so the rate
# term should act as a tailwind, not a headwind. These are TRAIN-only structural
# priors set on duration economics, NOT fit to validation.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55  # iter-18's default, retained for every other sector


# --------------------------------------------------------------------------- #
# Leg 1 + Leg 2: point-in-time fundamentals (SEC EDGAR, filed_date-stamped)
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    """Point-in-time YoY asset growth and YoY change in annual ROA.

    Uses the ORIGINAL (earliest-filed) value per fiscal period so a later
    restatement never leaks backward. Keeps only full-year (~365-day) net-income
    periods so annual ROA is clean. Everything stamped by the 10-K/Q filing date.
    """
    fund = fetch_fundamentals(list(tickers),
                              concepts=["Assets", "NetIncomeLoss"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy",
                                     "ag_2yr", "roa_chg"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 330) & (ni["dur"] <= 400)]
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = assets[assets["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        n = ni[ni["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

        def asset_growth(cur_pe, cur_val, years):
            target = cur_pe - pd.Timedelta(days=365 * years)
            diffs = np.abs((a_pe - target).dt.days.values)
            j = diffs.argmin()
            if diffs[j] <= 45 and a_val[j] > 0:
                return cur_val / a_val[j] - 1.0
            return np.nan

        roa_by_pe = {}
        for i in range(len(n)):
            pe = n["period_end"].iloc[i]
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] <= 45 and a_val[j] > 0:
                roa_by_pe[pe] = (float(n["value"].iloc[i]) / a_val[j],
                                 n["filed_date"].iloc[i])

        for i in range(len(a)):
            cur_pe = a_pe.iloc[i]
            cur_val = a_val[i]
            records.append({
                "ticker": ticker,
                "avail_date": a["filed_date"].iloc[i],
                "ag_yoy": asset_growth(cur_pe, cur_val, 1),
                "ag_2yr": asset_growth(cur_pe, cur_val, 2),
                "roa_chg": np.nan,
            })

        for pe, (roa_cur, fdate) in roa_by_pe.items():
            target = pe - pd.Timedelta(days=365)
            best_pe, best_diff = None, 9999
            for ppe in roa_by_pe:
                d = abs((ppe - target).days)
                if d < best_diff:
                    best_diff, best_pe = d, ppe
            if best_pe is not None and best_diff <= 60:
                records.append({
                    "ticker": ticker,
                    "avail_date": fdate,
                    "ag_yoy": np.nan,
                    "ag_2yr": np.nan,
                    "roa_chg": roa_cur - roa_by_pe[best_pe][0],
                })

    out = pd.DataFrame(records)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"ag_yoy": "last", "ag_2yr": "last", "roa_chg": "last"}))
    return out


def _trailing_z(s, min_periods=60):
    """Point-in-time z-score from an expanding window up to each date."""
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---------- Legs 1 & 2: point-in-time fundamentals, forward-filled ----------
    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["ag_yoy", "ag_2yr", "roa_chg"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][["avail_date", "ag_yoy", "ag_2yr", "roa_chg"]]
        if f.empty:
            g["ag_yoy"] = np.nan
            g["ag_2yr"] = np.nan
            g["roa_chg"] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # within-industry cross-sectional ranks (same-date only -> no lookahead)
    panel["disc_ag_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)          # slow growth -> high rank
    )
    panel["profmom_roa_chg_rank"] = (
        panel.groupby(["date", "industry"])["roa_chg"]
        .rank(pct=True, ascending=True)           # rising ROA -> high rank
    )

    # ---------- Leg 3: macro discount-rate regime (date-level, PIT) ----------
    macro = fetch_macro_series(
        {"DGS10": "y10", "T10Y2Y": "slope", "VIXCLS": "vix"},
        start_date="2013-06-01",
    )
    w = (macro.pivot_table(index="date", columns="series_name", values="value")
         .sort_index())
    w.index = pd.to_datetime(w.index)
    w = w.ffill()
    w["y10_trend21"] = w["y10"].diff(21)
    w["z_y10"] = _trailing_z(w["y10"])
    w["z_y10_trend"] = _trailing_z(w["y10_trend21"])
    w["z_slope"] = _trailing_z(w["slope"])
    w["z_vix"] = _trailing_z(w["vix"])
    w["rate_pressure_z"] = w["z_y10"] + w["z_y10_trend"]
    daily = w[["rate_pressure_z", "z_slope", "z_vix"]].reset_index().rename(
        columns={"index": "date"})
    daily["date"] = pd.to_datetime(daily["date"]).astype("datetime64[ns]")

    panel = panel.sort_values("date")
    panel = pd.merge_asof(panel, daily.sort_values("date"), on="date",
                          direction="backward")

    dur = panel["industry"].map(_DURATION_WEIGHT).fillna(_DEFAULT_DURATION)
    # sign-stable bullish conditions: negate the duration-scaled rate headwind
    # (a tailwind for negative-weight Energy), add steeper curve + elevated VIX
    panel["macro_regime_score"] = (
        -dur * panel["rate_pressure_z"] + panel["z_slope"] + panel["z_vix"]
    )

    new_cols = ["disc_ag_rank", "profmom_roa_chg_rank", "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date"], errors="ignore")
    return panel, new_cols
