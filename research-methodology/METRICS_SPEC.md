# Metrics spec: internal vs. external

Two separate metric families, kept deliberately apart so the dashboard stays
readable to non-technical viewers while the research loop keeps its rigor.

## Decision log

- **2026-08-02** — Dashboard metrics were confusing to outside viewers
  (tested_score, IC-Spearman, precision/recall, per-model, per-industry all
  shown at once, unexplained). Decided to split into an **external** metric
  (dashboard-facing, one number, plain English) and **internal** metrics
  (research-facing, drive what gets tested/kept, moved to a collapsed
  technical-details view + a dedicated Metrics page).
- External metric design iterated through three shapes before landing:
  1. "$500 spread across everything" — rejected, unclear how you'd literally
     split $500 across ~150 tickers.
  2. "top 5 vs bottom 5" — an improvement (apples to apples), but compares
     the model's picks to its own worst picks rather than to a real baseline.
  3. **Settled**: top 5 picks vs. the average return of every stock the model
     was choosing from that period ("the market it had to choose from"),
     applied as a *rate* to a $500 baseline rather than a literal split.
     Avoids the split problem entirely and is a fairer baseline than
     comparing against the model's own bottom picks.
- Internal metrics are unchanged in substance — this was a display/framing
  decision, not a research-methodology change. `tested_score` still gates
  everything the researcher does; nothing here can influence it.

## External metric — the one on the dashboard

**Top 5 picks vs. the eligible universe, on $500.**

Every 21 trading days (matching the label horizon — no overlapping periods,
so no return gets counted twice), take the model's top-5-ranked stocks that
day and see what $500 split across them would have returned by the next
rebalance. Compare against the same $500 split evenly across *every* stock
the model was choosing from that day. Compound both across the full
backtest. The gap between the two ending balances is the number shown.

- Implementation: [`core/monetary_metric.py`](../core/monetary_metric.py),
  `top5_vs_universe()`.
- Input: each experiment's already-saved `oos_rows.csv` (out-of-sample rows
  from `core/evaluator.walk_forward_eval`) — validation-split only, never the
  sealed holdout.
- Always shown with a disclaimer: **historical backtest, not a forecast; no
  trading costs, taxes, or slippage.**
- This metric is descriptive only. It does not feed back into which signals
  get tested, kept, or combined into live candidates — that stays entirely
  driven by `tested_score`.

## Internal metrics — research-only, drive feature decisions

Live in `core/evaluator.py`, journaled per experiment, shown on the
dashboard's Metrics page and in each experiment's collapsed technical
details.

| Metric | What it is | Role |
|---|---|---|
| **tested_score** (PR-AUC uplift) | Out-of-sample PR-AUC minus the base rate, from a purged walk-forward validation (6 expanding folds, 21-day purge gap). | The official ranking number — what the researcher optimizes for and what decides whether a signal is kept. |
| **ic_spearman** | Spearman rank correlation between predicted P(up) and realized forward return, pooled across the validation set. | Diagnostic: does the ranking track the *size* of the move, not just direction. Known limitation: pooled, not per-day — a genuine per-day IC is a future improvement, not yet built. |
| **precision / recall** | Standard classifier stats at the 0.5 confidence cutoff. | Descriptive snapshot only; nothing is ranked on a fixed cutoff since the product ranks continuously. |
| **cross-model comparison** | Same feature, same folds, scored independently by logistic regression (official), random forest, and gradient-boosted trees. | Robustness check — an edge only one model family sees is suspicious. |
| **per-industry breakdown** | The identical walk-forward protocol re-run independently per sector. | Robustness check — flags edges concentrated in one sector rather than broad-based. |
| **holdout / Gate 1** | Same PR-AUC-uplift calculation, run exactly once at the end of a run on data never touched during search. | The final generalization gate. Validation-to-holdout gap is the real verdict on overfitting. |

## Where each lives on the dashboard

- **Hero card, Signals tab, Experiment detail "verdict"** — external metric
  only.
- **Experiment detail → "technical details" expander** — full internal
  metrics JSON, unchanged.
- **New Metrics page** — both families explained in plain language, 2-3
  sentences each.
