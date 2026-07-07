"""Iteration 9 signal: capital-discipline x profitability-momentum interaction.

This deliberately fuses my two best, most sector-consistent orthogonal winners
into ONE feature family with a shared rationale:

  - iter 5 asset_growth (capital discipline): slow YoY asset growth -> bullish.
    Best signal so far (GBM +0.054), first to hold a positive sign in ALL sectors.
  - iter 8 profitability_acceleration (ROA change / fundamental momentum):
    rising trailing ROA -> bullish. Most sector-consistent signal (positive
    logistic uplift in Tech, Pharma AND Financials).

Both are non-price, slow-moving balance-sheet/income signals; both use the
Assets denominator so they keep clean coverage across banks (Financials keeps
inverting margin/CFOA ratios, but ROA and asset-growth generalise to leverage).

The NEW economic idea is the INTERACTION, not either leg alone. Capital
discipline is only a quality tell when the shrinking/steady asset base is being
made *more* productive: a firm that grows assets slowly AND is lifting its
return-on-assets is genuinely compounding quality (disciplined + improving),
while slow growth with falling ROA is a stagnating business, and fast asset
growth is only forgivable when profitability is accelerating with it. A single
monotone factor cannot express "disciplined AND improving"; a tree can, given
both legs and their product. Iter 7 proved that AVERAGING legs into one monotone
composite destroys the linear signal, so here the raw legs and their ranks are
kept SEPARATE and only an explicit product term is added for the interaction.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                ".claude", "skills", "research-methodology", "scripts"))
import numpy as np
import pandas as pd
from data import fetch_fundamentals

SIGNAL_NAME = "capital_discipline_x_profit_momentum"
HYPOTHESIS = (
    "Capital discipline (slow asset growth) is a bullish quality tell only when "
    "the asset base is simultaneously being made more productive (rising "
    "return-on-assets); disciplined firms that are ALSO improving profitability "
    "are compounding quality the market prices in gradually, so they have a "
    "higher chance of a positive 21-day return, whereas slow growth with falling "
    "ROA signals stagnation. The predictive content is the interaction of the "
    "asset-growth and ROA-momentum factors — both industry-ranked and built on "
    "an Assets denominator to stay valid across leveraged banks."
)


# --------------------------------------------------------------------------- #
# Point-in-time asset growth (from iter 5, proven).
# --------------------------------------------------------------------------- #
def _pit_asset_growth(tickers):
    fund = fetch_fundamentals(list(tickers), concepts=["Assets"])
    if fund.empty:
        return pd.DataFrame(columns=["ticker", "avail_date", "ag_yoy", "ag_2yr"])
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

            def growth(years):
                target = cur_pe - pd.Timedelta(days=365 * years)
                diffs = np.abs((grp["period_end"] - target).dt.days.values)
                j = diffs.argmin()
                if diffs[j] <= 45 and val[j] > 0:
                    return cur_val / val[j] - 1.0
                return np.nan

            records.append({
                "ticker": ticker,
                "avail_date": grp["filed_date"].iloc[i],
                "ag_yoy": growth(1),
                "ag_2yr": growth(2),
            })
    out = pd.DataFrame(records).dropna(subset=["ag_yoy"], how="all")
    out = (out.sort_values(["ticker", "avail_date"])
              .drop_duplicates(["ticker", "avail_date"], keep="last")
              .reset_index(drop=True))
    return out


# --------------------------------------------------------------------------- #
# Point-in-time ROA trend (from iter 8, proven).
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
        return pd.DataFrame(columns=["ticker", "avail_date", "pm_roa",
                                     "pm_roa_chg", "pm_roa_chg_2y"])
    fund = fund[fund["form"].isin(["10-K", "10-Q"])].copy()
    fund = fund.dropna(subset=["period_end", "filed_date", "value"])

    ni = fund[fund["concept"] == "NetIncomeLoss"].copy()
    ni = ni.dropna(subset=["period_start"])
    ni["dur"] = (ni["period_end"] - ni["period_start"]).dt.days
    ni = ni[(ni["dur"] >= 350) & (ni["dur"] <= 385)]
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


def add_feature(panel):
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).astype("datetime64[ns]")
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)

    tickers = panel["ticker"].unique()

    # ---- leg 1: capital discipline (asset growth) ----
    ag = _pit_asset_growth(tickers)
    if not ag.empty:
        ag["avail_date"] = pd.to_datetime(ag["avail_date"]).astype("datetime64[ns]")
        panel = _merge_pit(panel, ag, ["ag_yoy", "ag_2yr"])
    else:
        panel["ag_yoy"] = np.nan
        panel["ag_2yr"] = np.nan

    # ---- leg 2: profitability momentum (ROA change) ----
    roa = _pit_roa_trend(tickers)
    if not roa.empty:
        roa["avail_date"] = pd.to_datetime(roa["avail_date"]).astype("datetime64[ns]")
        panel = _merge_pit(panel, roa, ["pm_roa", "pm_roa_chg", "pm_roa_chg_2y"])
    else:
        panel["pm_roa"] = np.nan
        panel["pm_roa_chg"] = np.nan
        panel["pm_roa_chg_2y"] = np.nan

    # ---- industry-relative ranks (same-date only -> no lookahead) ----
    # Higher rank = SLOWER asset growth = more capital-disciplined = bullish.
    panel["cdpm_disc_rank"] = (
        panel.groupby(["date", "industry"])["ag_yoy"]
        .rank(pct=True, ascending=False)
    )
    # Higher rank = larger ROA improvement = bullish.
    panel["cdpm_prof_rank"] = (
        panel.groupby(["date", "industry"])["pm_roa_chg"]
        .rank(pct=True, ascending=True)
    )

    # ---- the NEW content: the interaction of the two bullish ranks ----
    # Both ranks are oriented so higher = more bullish and centred at 0.5, so
    # the product of the mean-centred ranks is large-positive only when a name is
    # BOTH disciplined AND improving (or both weak), and negative when the two
    # disagree. This is the "disciplined AND improving" cell a single monotone
    # factor cannot express; trees also get the raw legs above to split freely.
    d = panel["cdpm_disc_rank"] - 0.5
    p = panel["cdpm_prof_rank"] - 0.5
    panel["cdpm_interaction"] = d * p

    new_cols = [
        "ag_yoy", "ag_2yr", "pm_roa", "pm_roa_chg", "pm_roa_chg_2y",
        "cdpm_disc_rank", "cdpm_prof_rank", "cdpm_interaction",
    ]
    return panel, new_cols
