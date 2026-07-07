"""Iteration 12 signal: monotone quality-composite z-score.

Eleven iterations produced one unambiguous lesson: EVERY slow-moving fundamental
I test scores negative/flat on the judged LOGISTIC model but positive on the
trees (GBM +0.02..+0.10). The alpha is real but the linear judge can't see it,
because raw accounting ratios are non-monotone in probability-of-up (thresholds
and interactions, not a straight line). The only two signals that EVER cleared
logistic — asset_growth (iter 5) and ROA-change (iter 8) — did so precisely
because they carried a strong *monotone* raw gradient after an industry rank.

So this iteration does NOT introduce a new economic axis. It re-expresses the
three legs I already know carry a positive, sector-consistent tree edge as ONE
signal that is monotone in P(up) *by construction*, so the logistic judge can
finally price it:

  leg 1  capital discipline   :  slow YoY asset growth        (iter 5, GBM +0.054)
  leg 2  profitability momentum:  rising trailing ROA          (iter 8, GBM +0.017, all-sector +)
  leg 3  earnings safety      :  low dispersion of ROA         (iter 11, GBM +0.021)

Each leg is (a) sign-aligned so "higher = more bullish", (b) standardized
CROSS-SECTIONALLY within (date, industry) — neutralising the bank/Tech/Pharma
accounting-level gaps that flipped signs in iters 1-2/4/6 — and (c) averaged into
a single additive z-score. Averaging sign-aligned z-scores cancels idiosyncratic
accounting noise and, unlike raw ratios, produces a quantity that rises
monotonically with quality, so a single linear coefficient can express it. All
three legs use an Assets/NetIncome denominator so they stay well-defined for
leveraged banks (the reason iter 8's ROA-change held a positive sign in ALL
three sectors, unlike margin/CFOA ratios).

Economic rationale: cash-backed, capital-disciplined, consistently-profitable
firms are a latent "quality" trait the price-fixated market underweights; such
firms are relatively underpriced and drift up over the next 21 days, while
capital-indiscriminate, deteriorating, erratic earners fade.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals

SIGNAL_NAME = "quality_composite_zscore"
HYPOTHESIS = (
    "Capital-disciplined, consistently-profitable firms with improving "
    "return-on-assets are a latent 'quality' trait the price-fixated market "
    "underweights, so they are relatively underpriced and drift up over the next "
    "21 days. Expressed as a single additive z-score of three sign-aligned, "
    "industry-standardized legs (slow asset growth, rising ROA, low ROA "
    "dispersion) it is monotone in probability-of-up by construction — the form a "
    "linear model can actually price."
)


# --------------------------------------------------------------------------- #
# leg 1 — point-in-time asset growth (from iter 5, proven).
# --------------------------------------------------------------------------- #
def _pit_asset_growth(tickers):
    fund = fetch_fundamentals(list(tickers), concepts=["Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])
    fund = fund[fund["value"] > 0]

    records = []
    for ticker, grp in fund.groupby("ticker"):
        grp = (grp.sort_values("filed_date")
                  .drop_duplicates("period_end", keep="first")
                  .sort_values("period_end")
                  .reset_index(drop=True))
        val = grp["value"].astype(float).values
        for i in range(len(grp)):
            cur_pe = grp["period_end"].iloc[i]
            cur_val = val[i]
            target = cur_pe - pd.Timedelta(days=365)
            diffs = np.abs((grp["period_end"] - target).dt.days.values)
            j = diffs.argmin()
            ag = cur_val / val[j] - 1.0 if (diffs[j] <= 45 and val[j] > 0) else np.nan
            records.append({
                "ticker": ticker,
                "avail_date": grp["filed_date"].iloc[i],
                "ag_yoy": ag,
            })
    out = pd.DataFrame(records).dropna(subset=["ag_yoy"])
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


# --------------------------------------------------------------------------- #
# legs 2 & 3 — point-in-time ROA level/change (iter 8) and ROA dispersion (iter 11).
# --------------------------------------------------------------------------- #
def _nearest(period_ends, values, target, tol_days=50):
    diffs = np.abs((pd.to_datetime(pd.Series(list(period_ends))) - target).dt.days.values)
    j = int(np.argmin(diffs))
    if diffs[j] <= tol_days:
        return values[j], j
    return np.nan, -1


def _pit_roa_trend(tickers):
    fund = fetch_fundamentals(list(tickers), concepts=["NetIncomeLoss", "Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "pm_roa_chg", "es_roa_std"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 350) & (ni["dur"] <= 385)]          # annual net income
    ni = (ni.sort_values("filed_date")
            .drop_duplicates(["ticker", "period_end"], keep="first")
            .sort_values("period_end"))

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

        pe_list, roa_list, filed_list = [], [], []
        for i in range(len(ni_t)):
            cur_pe = ni_t["period_end"].iloc[i]
            ni_val = float(ni_t["value"].iloc[i])
            a_val, j = _nearest(as_pe, as_val, cur_pe, tol_days=50)
            if not np.isfinite(a_val) or a_val <= 0:
                continue
            pe_list.append(cur_pe)
            roa_list.append(ni_val / a_val)
            filed_list.append(max(ni_t["filed_date"].iloc[i],
                                  as_t["filed_date"].iloc[j]))

        if not pe_list:
            continue
        pe_arr = pd.to_datetime(pd.Series(pe_list))
        roa_arr = np.array(roa_list, dtype=float)

        for i in range(len(pe_arr)):
            cur_pe = pe_arr.iloc[i]

            # leg 2: YoY change in annual ROA (profitability momentum)
            target = cur_pe - pd.Timedelta(days=365)
            diffs = np.abs((pe_arr - target).dt.days.values)
            k = int(np.argmin(diffs))
            roa_chg = roa_arr[i] - roa_arr[k] if (diffs[k] <= 60 and k != i) else np.nan

            # leg 3: dispersion of ROA over the trailing (up to 4) annual points,
            # using ONLY data available at/before this filing (i inclusive).
            window = roa_arr[max(0, i - 3): i + 1]
            roa_std = float(np.std(window, ddof=1)) if len(window) >= 3 else np.nan

            records.append({
                "ticker": ticker,
                "avail_date": filed_list[i],
                "pm_roa_chg": roa_chg,
                "es_roa_std": roa_std,
            })

    out = pd.DataFrame(records)
    if out.empty:
        return out
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


def _merge_pit(panel, feat, cols):
    """Backward point-in-time merge of `feat` (with avail_date) onto panel per ticker."""
    feat = feat.sort_values("avail_date")
    parts = []
    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date")
        f = feat[feat["ticker"] == ticker][["avail_date"] + cols]
        if f.empty:
            for c in cols:
                g[c] = np.nan
        else:
            g = pd.merge_asof(g, f, left_on="date", right_on="avail_date",
                              direction="backward")
            g = g.drop(columns=["avail_date"])
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


def _xs_zscore(panel, col):
    """Cross-sectional z-score within (date, industry). Neutralises sector-level
    accounting gaps and keeps the composite comparable across regimes."""
    grp = panel.groupby(["date", "industry"])[col]
    mean = grp.transform("mean")
    std = grp.transform("std")
    z = (panel[col] - mean) / std.replace(0.0, np.nan)
    return z.clip(-3.0, 3.0)          # cap outliers so no single print dominates


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    tickers = panel["ticker"].unique()

    # ---- raw point-in-time legs ----
    ag = _pit_asset_growth(tickers)
    if not ag.empty:
        ag["avail_date"] = pd.to_datetime(ag["avail_date"]).astype("datetime64[ns]")
        panel = _merge_pit(panel, ag, ["ag_yoy"])
    else:
        panel["ag_yoy"] = np.nan

    roa = _pit_roa_trend(tickers)
    if not roa.empty:
        roa["avail_date"] = pd.to_datetime(roa["avail_date"]).astype("datetime64[ns]")
        panel = _merge_pit(panel, roa, ["pm_roa_chg", "es_roa_std"])
    else:
        panel["pm_roa_chg"] = np.nan
        panel["es_roa_std"] = np.nan

    # ---- sign-aligned, industry-standardized z-scores (higher = more bullish) ----
    z_disc = -_xs_zscore(panel, "ag_yoy")        # slow asset growth  -> bullish
    z_prof = _xs_zscore(panel, "pm_roa_chg")     # rising ROA         -> bullish
    z_safe = -_xs_zscore(panel, "es_roa_std")    # low ROA dispersion -> bullish

    legs = pd.concat([z_disc, z_prof, z_safe], axis=1)
    legs.columns = ["qz_disc", "qz_prof", "qz_safe"]

    # ---- the signal: additive composite (mean of available legs) ----
    # nanmean so partial coverage still contributes; requires >=1 leg present.
    panel["qz_disc"] = legs["qz_disc"]
    panel["qz_prof"] = legs["qz_prof"]
    panel["qz_safe"] = legs["qz_safe"]
    panel["quality_z_composite"] = legs.mean(axis=1, skipna=True)

    # monotone industry rank of the composite (same-date only -> no lookahead),
    # a rank-space view of the identical ordering for robustness to scale.
    panel["quality_z_ind_rank"] = (
        panel.groupby(["date", "industry"])["quality_z_composite"]
        .rank(pct=True, ascending=True)
    )

    new_cols = [
        "qz_disc", "qz_prof", "qz_safe",
        "quality_z_composite", "quality_z_ind_rank",
    ]
    return panel, new_cols
