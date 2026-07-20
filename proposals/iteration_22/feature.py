"""Iteration 22 — FULL four-leg orthogonal BUNDLE: capital discipline +
profitability momentum + value (earnings yield) + macro discount-rate regime.

Campaign trajectory: the winning frame is a bundle of orthogonal factors scored
as ONE model. The three prior bundle configs each scored ~+0.057..+0.065
validation and each rescued a DIFFERENT part of the universe:
  * iter-20 (discipline + prof-momentum + macro): +0.0654 — campaign peak.
    Prof-momentum was an all-sector-positive contributor.
  * iter-21 (discipline + VALUE + macro): +0.0574 — value flipped
    CommunicationServices to +0.035 and lifted Materials to +0.059 (defensive
    breadth where the rate timer is inert), but dropping prof-momentum cost
    ~0.008 overall, and disc<->value correlation was measured at just 0.099.

Iter-21's closing read was explicit: value and prof-momentum proved orthogonal
to EACH OTHER (a valuation axis vs a quality/trajectory axis) and each rescued
different sectors, so running BOTH alongside discipline + macro should recover
iter-20's peak AND add value's CommServices/Materials breadth. That is exactly
this iteration: the full four-leg bundle, no leg swapping, no duration re-tuning
(the Energy negative-weight sign fix from iter-20 is kept as the one validated
macro correction; everything else defaults to iter-18's simpler map).

Why FOUR and not padding: the campaign has directly measured that these four
legs are pairwise low-correlation (see orthogonality below); this is not three
variations on one idea. The deeper HOLDOUT motivation: iter-16's LONE macro
timer scored +0.0521 validation but FAILED holdout (-0.0118) — a single
date-level time series is fragile. A bundle only de-risks that if its
CROSS-SECTIONAL legs carry regime-independent edge. Three independent
cross-sectional legs (discipline, prof-momentum, value) spread that risk far
more than one, reducing reliance on the macro timer doing the linear lifting.

DATA-TRAP HANDLING (why the value leg is point-in-time CLEAN):
  adj_close is fully split+dividend adjusted; EDGAR shares-outstanding is on the
  then-current basis. Multiplying them naively fabricates a huge fake "cheapness"
  for any name that later split (NVDA/AAPL/TSLA...). Market cap and E/P are
  split-INVARIANT, so I reconstruct shares on adj_close's current basis by
  detecting split-sized abrupt jumps (ratio >1.4 or <0.71) in the EDGAR share
  series and cumulating the forward split factor. This uses no future
  information in the economic sense (a split leaves market cap and E/P
  unchanged) and removes the trap.

Legs (each a genuinely different source of edge):
  1. Capital discipline  — within-industry rank of YoY asset growth (slow growth
     = capital-disciplined = bullish; Cooper-Gulen-Schill investment anomaly).
  2. Profitability momentum — within-industry rank of YoY change in return-on-
     assets; firms whose profit-PER-asset trajectory is improving are on a
     strengthening fundamental path the market prices in only gradually.
  3. Value / cheapness   — within-industry rank of trailing earnings yield
     (annual NetIncome / split-invariant market cap); cheap firms out-drift.
  4. Macro discount-rate regime — a sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight (structural
     priors; Energy negative because it co-moves POSITIVELY with yields).

Orthogonality (why each PAIR is low-correlation — different source of edge):
  * (1) vs (2): asset-base SIZE trajectory (a growth/investment axis) vs
    profit-PER-asset trajectory (a quality axis). They come from different
    financial statements — a slow-grower can have rising OR falling ROA, a fast
    expander likewise — so the balance-sheet-growth rank and the ROA-change rank
    are only weakly related.
  * (1) vs (3): asset-base SIZE trajectory vs the PRICE the market puts on
    current earnings (a valuation axis). A disciplined slow-grower can trade
    rich (defensive premium) or cheap (out-of-favor). Measured corr ~0.10 in
    iter-21's smoke test.
  * (2) vs (3): profit-trajectory (a quality/change axis, from the income
    statement over time) vs earnings-price LEVEL (a valuation axis, price vs a
    single trailing NI). Improving profitability can be expensive (glamour) or
    cheap (early turnaround) — different constructs, weakly related.
  * (1)/(2)/(3) vs (4): the three fundamental legs are cross-sectional (differ
    across names on a date, ~constant over weeks); the macro leg is a pure
    time-series scaled by a constant sector weight (identical across names within
    a sector, varies day to day) — near-zero correlation by construction.
    Fundamentals decide WHICH names, macro times WHEN the universe rises.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology",
                                "scripts"))
from data import fetch_fundamentals, fetch_macro_series  # noqa: E402

SIGNAL_NAME = "discipline_profmom_value_macro_bundle"
HYPOTHESIS = (
    "Capital discipline: firms that expand their asset base slowly are "
    "underpriced and drift up (overinvestment corrected gradually). "
    "Profitability momentum: firms whose annual return-on-assets is improving "
    "year-over-year are on a strengthening fundamental trajectory the market "
    "prices in only gradually. Value: firms priced cheaply relative to trailing "
    "earnings (high earnings yield) out-drift expensive glamour names as over-"
    "extrapolated pessimism reverses and the HML risk premium is earned — a "
    "regime-INDEPENDENT edge that works in defensive sectors where a rate timer "
    "is inert. Macro discount-rate regime: low/falling Treasury yields, a "
    "steepening curve and an elevated VIX risk premium are a sign-stable bullish "
    "backdrop, with the rate term scaled by each sector's cash-flow duration "
    "(Tech most hurt by rising yields; Energy an inflation/rate hedge whose "
    "returns co-move POSITIVELY with yields, hence a negative weight). "
    "Orthogonality — discipline (asset-SIZE trajectory, a growth/investment "
    "axis) vs prof-momentum (profit-PER-asset trajectory, a quality axis) come "
    "from different statements and move independently (slow growth pairs with "
    "rising or falling ROA); discipline vs value (price paid per dollar of "
    "earnings, a valuation axis) are near-uncorrelated (measured corr ~0.10, a "
    "slow-grower can be cheap or dear); prof-momentum vs value differ as a "
    "change/quality axis vs a price-LEVEL axis (improving firms can be cheap or "
    "glamour); and all three cross-sectional legs are near-uncorrelated with the "
    "macro leg, a single time-series identical across names within a sector on a "
    "given day — fundamentals decide WHICH names, macro times WHEN."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18's proven map plus iter-20's ONE
# validated correction — Energy carries a NEGATIVE weight because its returns
# co-move POSITIVELY with yields (inflation/rate hedge), turning the rate term
# into a tailwind.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55

_SPLIT_UP = 1.40    # abrupt share jump above this = split (not issuance)
_SPLIT_DN = 0.71    # abrupt share drop below this = reverse split (not buyback)


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: asset growth, annual ROA change, annual NetIncome,
# and split-invariant shares outstanding.  All stamped by filed_date.
# --------------------------------------------------------------------------- #
def _split_adjust_shares(df):
    """Express a per-ticker shares-outstanding series on adj_close's CURRENT
    basis by detecting split-sized abrupt jumps and cumulating the forward
    split factor.  df sorted ascending by period_end; returns adjusted values."""
    raw = df["value"].astype(float).values
    n = len(raw)
    mult = np.ones(n)  # per-step split multiplier at position i (vs i-1)
    for i in range(1, n):
        if raw[i - 1] > 0:
            r = raw[i] / raw[i - 1]
            if r >= _SPLIT_UP or r <= _SPLIT_DN:
                mult[i] = r
    fwd = np.ones(n)
    acc = 1.0
    for i in range(n - 1, -1, -1):
        fwd[i] = acc
        acc *= mult[i]
    return raw * fwd


def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "NetIncomeLoss", "CommonStockSharesOutstanding",
                  "WeightedAverageNumberOfDilutedSharesOutstanding"],
    )
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "ag_2yr",
                                     "roa_chg", "ni_annual", "shares_adj"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 330) & (ni["dur"] <= 400)]  # full-year only
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first"))

    shr = fund[fund["concept"].isin(
        ["CommonStockSharesOutstanding",
         "WeightedAverageNumberOfDilutedSharesOutstanding"])].copy()
    shr = shr[shr["value"] > 0]
    shr["_prio"] = (shr["concept"] != "CommonStockSharesOutstanding").astype(int)
    shr = (shr.sort_values(["_prio", "filed_date"])
              .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = assets[assets["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        n = ni[ni["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)
        s = shr[shr["ticker"] == ticker].sort_values("period_end").reset_index(drop=True)

        # ---- shares on adj_close's current split basis, by filing date ----
        if not s.empty:
            s = s.copy()
            s["shares_adj"] = _split_adjust_shares(s)
            for i in range(len(s)):
                records.append({
                    "ticker": ticker, "avail_date": s["filed_date"].iloc[i],
                    "ag_yoy": np.nan, "ag_2yr": np.nan, "roa_chg": np.nan,
                    "ni_annual": np.nan, "shares_adj": float(s["shares_adj"].iloc[i]),
                })

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

        for i in range(len(a)):
            records.append({
                "ticker": ticker, "avail_date": a["filed_date"].iloc[i],
                "ag_yoy": asset_growth(a_pe.iloc[i], a_val[i], 1),
                "ag_2yr": asset_growth(a_pe.iloc[i], a_val[i], 2),
                "roa_chg": np.nan, "ni_annual": np.nan, "shares_adj": np.nan,
            })

        # annual ROA (NI / assets) keyed by period_end, plus annual NI itself
        roa_by_pe = {}
        for i in range(len(n)):
            pe = n["period_end"].iloc[i]
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            ni_val = float(n["value"].iloc[i])
            fdate = n["filed_date"].iloc[i]
            roa = ni_val / a_val[j] if (diffs[j] <= 45 and a_val[j] > 0) else np.nan
            roa_by_pe[pe] = (roa, fdate)
            records.append({
                "ticker": ticker, "avail_date": fdate,
                "ag_yoy": np.nan, "ag_2yr": np.nan, "roa_chg": np.nan,
                "ni_annual": ni_val, "shares_adj": np.nan,
            })

        for pe, (roa_cur, fdate) in roa_by_pe.items():
            if not np.isfinite(roa_cur):
                continue
            target = pe - pd.Timedelta(days=365)
            best_pe, best_diff = None, 9999
            for ppe in roa_by_pe:
                d = abs((ppe - target).days)
                if d < best_diff and np.isfinite(roa_by_pe[ppe][0]):
                    best_diff, best_pe = d, ppe
            if best_pe is not None and best_diff <= 60:
                records.append({
                    "ticker": ticker, "avail_date": fdate,
                    "ag_yoy": np.nan, "ag_2yr": np.nan,
                    "roa_chg": roa_cur - roa_by_pe[best_pe][0],
                    "ni_annual": np.nan, "shares_adj": np.nan,
                })

    out = pd.DataFrame(records)
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"ag_yoy": "last", "ag_2yr": "last", "roa_chg": "last",
                    "ni_annual": "last", "shares_adj": "last"}))
    return out


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(panel["ticker"].unique())
    fpit = fpit.sort_values(["ticker", "avail_date"])
    for c in ["ag_yoy", "ag_2yr", "roa_chg", "ni_annual", "shares_adj"]:
        fpit[c] = fpit.groupby("ticker")[c].ffill()

    parts = []
    cols = ["avail_date", "ag_yoy", "ag_2yr", "roa_chg", "ni_annual", "shares_adj"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols]
        if f.empty:
            for c in cols[1:]:
                g[c] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # ---- Leg 1: capital discipline (slow asset growth -> high rank) ----
    panel["disc_ag_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)
    )

    # ---- Leg 2: profitability momentum (rising YoY ROA -> high rank) ----
    panel["profmom_roa_chg_rank"] = (
        panel.groupby(["date", "industry"])["roa_chg"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 3: value = trailing earnings yield on split-invariant mkt cap ----
    mktcap = panel["adj_close"] * panel["shares_adj"]
    panel["earnings_yield"] = np.where(mktcap > 0,
                                       panel["ni_annual"] / mktcap, np.nan)
    panel["value_ey_rank"] = (
        panel.groupby(["date", "industry"])["earnings_yield"]
        .rank(pct=True, ascending=True)          # high E/P (cheap) -> high rank
    )

    # ---------- Leg 4: macro discount-rate regime (date-level, PIT) ----------
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
    panel["macro_regime_score"] = (
        -dur * panel["rate_pressure_z"] + panel["z_slope"] + panel["z_vix"]
    )

    new_cols = ["disc_ag_rank", "profmom_roa_chg_rank", "value_ey_rank",
                "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "shares_adj", "ni_annual",
                                "earnings_yield"], errors="ignore")
    return panel, new_cols
