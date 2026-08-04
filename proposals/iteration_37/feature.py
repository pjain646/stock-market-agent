"""Iteration 37 — three-leg orthogonal BUNDLE across THREE genuinely different
data domains: capital-structure LEVEL (fundamental) + INSIDER NET-BUYING
(private-information / behavioural) + macro discount-rate REGIME (timing).

WHY THIS BUNDLE, AND WHY IT IS NEW
----------------------------------
The journal's most-repeated lesson is that the macro TIMING leg carries the
campaign's proven edge, and that swapping in yet another cross-sectional
VALUE/QUALITY fundamental (iters 24-34) or ADDING a fourth cross-sectional leg
(iters 22, 36) only dilutes the +0.075 solvency+profmom+macro peak — because a
second accounting/price factor shares the same regime exposure and the logistic
loses degrees of freedom without net new information.

The single data domain the ENTIRE campaign has never touched is INSIDER
TRANSACTIONS (SEC Form 4). Every prior leg came from balance sheets, income
statements, past prices, or FRED. Insider net open-market buying is a
fundamentally different SOURCE of edge: it is the revealed private view of the
people who know the business best (officers/directors), a signal the base model
and every prior bundle has no access to. That makes it the highest-information
untested experiment and a genuine diversifier — not a variation on any axis
already tried.

This bundle keeps the two proven workhorses (solvency LEVEL + macro TIMING) and
SWAPS the profitability-momentum leg for an insider net-buying leg (three legs,
not four — the journal shows a fourth cross-sectional leg cannibalises).

THE THREE LEGS (each a genuinely different source of edge):
  1. Equity-to-assets solvency (PROVEN) — within-industry rank of
     StockholdersEquity / Assets. Low leverage / low distress risk; the distress
     anomaly says highly-levered firms under-perform risk-adjusted. A
     capital-structure LEVEL axis, strictly point-in-time from filed 10-K/10-Q
     balance sheets (non-positive book equity excluded; ranked WITHIN
     (date, industry)).
  2. Insider net-buying (NEW) — within-industry rank of trailing-180-day net
     insider dollar flow: sum of open-market PURCHASE value (code P, +) minus
     open-market SALE value (code S, -) from Form 4 filings, counted only once
     each filing is PUBLIC (filing_date <= row date), a strict point-in-time
     rolling window. Insiders buy with their own money almost only when they
     believe the stock is cheap relative to private information; the
     insider-purchase anomaly (Lakonishok-Lee; Cohen-Malloy-Pomorski) says
     net-bought names out-drift. A PRIVATE-INFORMATION / behavioural axis with no
     accounting-ratio or macro input at all.
  3. Macro discount-rate regime (PROVEN) — sign-stable bullish-conditions score
     (low/falling 10y yield, steeper curve, elevated VIX risk premium) with the
     rate term scaled by a per-sector cash-flow-duration weight. A market-timing
     axis (WHEN).

ORTHOGONALITY (why each PAIR is low-correlation — a different edge, not a
variation on the same idea):
  * (1) solvency vs (2) insider buying: solvency is a slow accounting STOCK
    describing how the firm is FINANCED; insider buying is an event-driven
    BEHAVIOURAL flow describing what management is DOING with its own money right
    now. A rock-solid, low-leverage firm can see zero insider buying, and heavy
    insider buying often clusters in beaten-down / distressed names where
    managers see value the market missed — so the two ranks load different names
    and are near-uncorrelated. Different data domains (balance sheet vs Form 4),
    different time character (months-constant vs event-driven).
  * (2) insider buying vs (3) macro: insider flow is cross-sectional (differs
    across names on a date); the macro leg is a single time-series scaled by a
    constant sector weight (identical across names within a sector that day), so
    ~zero correlation by construction.
  * (1) solvency vs (3) macro: proven near-zero in the campaign's +0.075 frame
    (cross-sectional accounting level vs date-level macro series).
  fundamentals + insider pick WHICH names, macro times WHEN.
NOTE: prof-momentum is deliberately swapped OUT (not stacked) to keep three
orthogonal axes and avoid the fourth-leg cannibalisation the journal documents.
No macro-free two-fundamental pair is proposed — that space has failed.
"""

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology",
                                "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "research-methodology", "scripts"))
from data import (fetch_fundamentals, fetch_macro_series,  # noqa: E402
                  fetch_insider_transactions)

SIGNAL_NAME = "solvency_insider_macro_bundle"
HYPOTHESIS = (
    "Equity-to-assets solvency (PROVEN): high book-equity/total-assets means low "
    "leverage and low distress risk; the distress anomaly says highly levered "
    "firms under-perform risk-adjusted, so solvent firms out-drift — a "
    "capital-structure LEVEL axis, point-in-time from filed 10-K/10-Q balance "
    "sheets, non-positive book equity excluded so the ratio cannot sign-invert, "
    "ranked within industry. Insider net-buying (NEW to the campaign): trailing "
    "180-day net insider dollar flow (open-market PURCHASE value minus SALE value "
    "from Form 4, counted only once each filing is public) — insiders buy with "
    "their own money almost only when they believe the stock is cheap relative to "
    "private information, and the insider-purchase anomaly says net-bought names "
    "out-drift; a PRIVATE-INFORMATION / behavioural axis, ranked within industry, "
    "the ONE data domain no prior bundle has ever used. Macro discount-rate "
    "regime (PROVEN): low/falling Treasury yields, a steeper curve and an "
    "elevated VIX risk premium are a sign-stable bullish backdrop, the rate term "
    "scaled by each sector's cash-flow duration (Tech most hurt by rising yields; "
    "Energy an inflation/rate hedge, hence a negative weight) — a market-TIMING "
    "axis. Orthogonality: (solvency vs insider) a slow accounting STOCK of how "
    "the firm is FINANCED vs an event-driven BEHAVIOURAL flow of what management "
    "is DOING with its own money — different data domains (balance sheet vs Form "
    "4), and insider buying clusters in beaten-down names where solvency says "
    "little, so the two ranks load different names and are near-uncorrelated. "
    "(insider vs macro) insider flow is cross-sectional while macro is one "
    "time-series identical across names within a sector on a day, ~zero by "
    "construction. (solvency vs macro) proven near-zero in the +0.075 frame. "
    "Fundamentals+insider pick WHICH names, macro times WHEN."
)

# Structural cash-flow-duration weights (train-only priors on duration
# economics, NOT fit to validation): iter-18/20's proven map.
_DURATION_WEIGHT = {
    "Technology": 1.00,
    "Pharma": 0.30,
    "Energy": -0.40,
}
_DEFAULT_DURATION = 0.55

_INSIDER_WINDOW_DAYS = 180


# --------------------------------------------------------------------------- #
# Point-in-time fundamentals: equity-to-assets solvency, stamped by filed_date.
# --------------------------------------------------------------------------- #
def _pit_fundamentals(tickers):
    fund = fetch_fundamentals(
        list(tickers),
        concepts=["Assets", "StockholdersEquity"],
    )
    empty = pd.DataFrame(columns=["ticker", "avail_date", "eq_to_assets"])
    if fund.empty:
        return empty
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    assets = fund[fund["concept"] == "Assets"].copy()
    assets = assets[assets["value"] > 0]
    assets = (assets.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    equity = fund[fund["concept"] == "StockholdersEquity"].copy()
    equity = (equity.sort_values("filed_date")
                    .drop_duplicates(["ticker", "period_end"], keep="first"))

    records = []
    for ticker in pd.unique(fund["ticker"]):
        a = (assets[assets["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        e = (equity[equity["ticker"] == ticker]
             .sort_values("period_end").reset_index(drop=True))
        if a.empty:
            continue
        a_pe = a["period_end"]
        a_val = a["value"].astype(float).values

        for i in range(len(e)):
            pe = e["period_end"].iloc[i]
            eq_val = float(e["value"].iloc[i])
            if not np.isfinite(eq_val) or eq_val <= 0:
                continue
            diffs = np.abs((a_pe - pe).dt.days.values)
            j = diffs.argmin()
            if diffs[j] > 45 or a_val[j] <= 0:
                continue
            ratio = eq_val / a_val[j]
            ratio = min(max(ratio, 0.0), 1.0)
            fdate = max(e["filed_date"].iloc[i], a["filed_date"].iloc[j])
            records.append({
                "ticker": ticker, "avail_date": fdate, "eq_to_assets": ratio,
            })

    out = pd.DataFrame(records)
    if out.empty:
        return empty
    out["avail_date"] = pd.to_datetime(out["avail_date"])
    out = out.sort_values("avail_date")
    out = (out.groupby(["ticker", "avail_date"], as_index=False)
              .agg({"eq_to_assets": "last"}))
    return out


# --------------------------------------------------------------------------- #
# Point-in-time insider net-buying: trailing-180d net open-market dollar flow,
# available only once a Form 4 is public (filing_date <= row date).
# --------------------------------------------------------------------------- #
def _pit_insider_events(tickers):
    """Return per-ticker signed dollar events keyed by public filing_date."""
    cols = ["ticker", "filing_date", "signed_value"]
    try:
        ins = fetch_insider_transactions(list(tickers))
    except Exception:
        return pd.DataFrame(columns=cols)
    if ins is None or ins.empty:
        return pd.DataFrame(columns=cols)

    ins = ins.copy()
    # Keep ONLY open-market purchases (P) and sales (S) — the discretionary,
    # information-bearing trades. Grants (A), option exercises (M), tax
    # withholding (F) are non-informational and excluded.
    ins = ins[ins["transaction_code"].isin(["P", "S"])].copy()
    if ins.empty:
        return pd.DataFrame(columns=cols)

    ins["filing_date"] = pd.to_datetime(ins["filing_date"])
    ins["shares"] = pd.to_numeric(ins["shares"], errors="coerce")
    ins["price_per_share"] = pd.to_numeric(ins["price_per_share"], errors="coerce")
    ins = ins.dropna(subset=["filing_date", "shares"])
    ins = ins[ins["shares"] > 0]
    if ins.empty:
        return pd.DataFrame(columns=cols)

    # Dollar value; fall back to each ticker's median transaction price when a
    # Form 4 omits price_per_share, so a missing price doesn't zero the trade.
    med_price = ins.groupby("ticker")["price_per_share"].transform("median")
    price = ins["price_per_share"].fillna(med_price)
    price = price.fillna(price.median())  # last-resort global median
    ins["value"] = ins["shares"] * price

    sign = np.where(ins["transaction_code"] == "P", 1.0, -1.0)
    ins["signed_value"] = sign * ins["value"]

    # Collapse to one signed total per (ticker, filing_date).
    ev = (ins.groupby(["ticker", "filing_date"], as_index=False)["signed_value"]
             .sum())
    return ev[cols].sort_values(["ticker", "filing_date"]).reset_index(drop=True)


def _rolling_net_insider(panel, events):
    """For each panel row, sum signed insider dollar flow over the trailing
    _INSIDER_WINDOW_DAYS whose filing_date <= row date. Point-in-time by
    construction. Names/dates with no insider events get 0.0 (neutral)."""
    panel = panel.copy()
    panel["insider_net_180d"] = 0.0
    if events.empty:
        return panel

    win = pd.Timedelta(days=_INSIDER_WINDOW_DAYS)
    ev_by_ticker = {t: g for t, g in events.groupby("ticker")}

    out_vals = np.zeros(len(panel), dtype=float)
    # panel already sorted by ticker,date upstream; iterate groups by position.
    for t, g in panel.groupby("ticker", sort=False):
        ev = ev_by_ticker.get(t)
        idx = g.index.values
        if ev is None or ev.empty:
            continue
        fdates = ev["filing_date"].values.astype("datetime64[ns]")
        csum = np.concatenate([[0.0], np.cumsum(ev["signed_value"].values)])
        dates = g["date"].values.astype("datetime64[ns]")
        lo = (g["date"] - win).values.astype("datetime64[ns]")
        # events with filing_date <= date  (right side)
        hi_i = np.searchsorted(fdates, dates, side="right")
        # events with filing_date <= date-window (left side, exclusive window)
        lo_i = np.searchsorted(fdates, lo, side="right")
        out_vals[idx] = csum[hi_i] - csum[lo_i]

    panel["insider_net_180d"] = out_vals
    return panel


def _trailing_z(s, min_periods=60):
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std()
    return (s - mu) / sd


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)

    tickers = panel["ticker"].unique()

    # ---------- Leg 2: insider net-buying (Form 4), point-in-time ----------
    events = _pit_insider_events(tickers)
    panel = _rolling_net_insider(panel, events)

    # ---------- point-in-time fundamentals, forward-filled per ticker ----------
    fpit = _pit_fundamentals(tickers)
    fpit = fpit.sort_values(["ticker", "avail_date"])
    if not fpit.empty:
        fpit["eq_to_assets"] = fpit.groupby("ticker")["eq_to_assets"].ffill()

    parts = []
    cols = ["avail_date", "eq_to_assets"]
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = fpit[fpit["ticker"] == ticker][cols] if not fpit.empty else None
        if f is None or f.empty:
            g["eq_to_assets"] = np.nan
        else:
            g = pd.merge_asof(g, f.sort_values("avail_date"),
                              left_on="date", right_on="avail_date",
                              direction="backward")
        parts.append(g)
    panel = pd.concat(parts, ignore_index=True)

    # ---- Leg 1: solvency (high equity/assets -> high rank -> bullish) ----
    panel["solvency_eq_assets_rank"] = (
        panel.groupby(["date", "industry"])["eq_to_assets"]
        .rank(pct=True, ascending=True)
    )

    # ---- Leg 2: insider net-buy rank (more net buying -> high rank -> bullish)
    panel["insider_net_buy_rank"] = (
        panel.groupby(["date", "industry"])["insider_net_180d"]
        .rank(pct=True, ascending=True)
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
    panel["macro_regime_score"] = (
        -dur * panel["rate_pressure_z"] + panel["z_slope"] + panel["z_vix"]
    )

    new_cols = ["solvency_eq_assets_rank", "insider_net_buy_rank",
                "macro_regime_score"]

    panel = panel.drop(columns=["rate_pressure_z", "z_slope", "z_vix",
                                "avail_date", "eq_to_assets",
                                "insider_net_180d"],
                       errors="ignore")
    return panel, new_cols
