---
name: research-methodology
description:
  Methodology for analyzing stocks, signals, and markets with senior-analyst
  depth and honest method. Use this whenever analyzing a company or stock,
  designing or judging a trading or investing signal, reading an earnings
  report, assessing risk, comparing names, or giving a data-grounded market
  read. It teaches how to think one level deeper (decompose drivers, name
  mechanisms, seek disconfirming evidence), the fundamental dimensions to probe
  (growth quality, margins, balance sheet, moat, valuation, management,
  downside), the statistical rigor to prove a signal real (factor-adjustment,
  decile gradients, significance bars, out-of-sample testing), point-in-time
  and data-trap handling, and the honesty guardrails (tested over asserted, no
  fabrication, no lookahead). Consult it for any serious market analysis,
  one-off or repeated.
---

# Market Research & Analysis — Methodology

Read this before analyzing a stock, a signal, or a market. It does two things: gives you a way to think *deeper* than a surface read, and enforces the honesty that makes a conclusion worth trusting. The gap between a junior take and a senior one is not how many metrics you list — it's how many layers down you go, and how honestly you test what you find.

## Think one level deeper

This is the engine. For every fact, metric, or claim, don't stop at the number — ask the question behind it. That habit, applied relentlessly, *is* deep analysis.

- **Decompose.** "Revenue grew 20%" is the start, not the finding. Volume, price, mix, or acquisition? Organic or one-time? Accelerating or slowing? A number you haven't broken into its drivers is a headline, not an insight.
- **Name the mechanism.** Don't say "wide moat" or "strong margins" — name the specific cause (switching costs, network effects, scale, IP, pricing power) and the evidence it's actually holding (share, churn, pricing). A claim with no mechanism is a vibe.
- **Ask what would break it.** For any thesis, state the 2–3 things that would have to go wrong, and actively hunt the disconfirming evidence. Steelman the other side before you conclude. The fastest route to a shallow take is gathering only what agrees with you.
- **Connect the threads.** Growth, margins, debt, and valuation are one system, not a checklist — fast growth funded by debt with thinning margins is a different story than each line read alone.
- **Quantify it.** Turn fuzzy judgments into explicit, falsifiable criteria — exact metrics, ratios, thresholds. "High quality" is an opinion; "ROIC above 15%, net-debt/EBITDA under 2, free-cash-flow positive five years running" is a claim you can actually be wrong about. Precision is what makes a view checkable instead of unfalsifiable.
- **Think in systems.** Nothing stands alone — a position interacts with what you already hold (correlation, concentration), and a "signal" interacts with factors you already own. Always ask what a result is *adding*, not just whether it's positive.
- **Find the load-bearing number.** Most theses hinge on one or two figures — a margin, a growth rate, free cash flow, a coverage ratio. Name it explicitly, verify it against the **primary source** (the actual filing, not just an aggregator that may be stale, wrong, or using a different definition), and state how the conclusion changes if it's off. A verdict that silently flips on an unverified number isn't a verdict — it's a guess wearing a number. When two reasonable people would disagree, it's usually because they're using different values for this one figure; pin it down.

Whenever you catch yourself listing, stop and push: *so what, and why?*

## What data to analyze

Cast a wide net before judging anything. The layered sources and what each is for:

- **Price & volume** — trend, momentum, volatility, liquidity. Most abundant data and the easiest to over-mine; treat raw technical patterns with extra skepticism.
- **Fundamentals** (cash flow, balance sheet, income) — the economic reality behind the price. Use point-in-time: as of the filing date, never the fiscal period.
- **Earnings dates & surprises** — catalysts, and how reality diverged from expectations.
- **News & sentiment** — context, but only from timestamped sources so you know when each item was public.
- **Macro & sector** — rates, cycle, sector rotation. A name rarely moves independently of its sector.

If a fetcher or data tool is available, use it; if not, reason explicitly from what you do and don't know rather than guessing.

## Reading a company (fundamental analysis)

Cover these dimensions — but as **probes, not a checklist**. For each, the win is the second-order question, not the headline number.

- **Growth quality** — not "is it growing" but what's driving it, how durable that driver is, and the unit economics underneath.
- **Margins & profitability** — what *structurally* supports them, and what competitive or input-cost force could compress them.
- **Balance sheet** — can it survive a bad year? Debt load, maturity wall, interest coverage, liquidity. Solvency through a downturn, not just today's snapshot.
- **Competitive position (moat)** — the specific defense mechanism, the evidence it's holding (pricing power, share, retention), and what would erode it. Benchmark against the *named* direct competitors actually taking or defending share on the decisive axis — not a vague "peers."
- **Valuation** — reverse-engineer it: what growth and margin assumptions does the current multiple *imply*, and are they reasonable vs. the company's history and quality-adjusted peers? A "cheap" multiple on deteriorating fundamentals is a value trap, not a bargain.
- **Management vs. the numbers** — separate what management *says* from what the financials *show*; the gaps are where the signal hides. On earnings: what beat or missed, what guidance changed, and whether it actually moves the thesis.
- **Downside & worst case** — the realistic bad scenario, not a generic risk list: the actual loss if the thesis is wrong, and the trigger that causes it.

For a head-to-head comparison, judge on like-for-like, quality-adjusted terms — the better risk-adjusted setup, not the lower headline multiple.

## Testing a signal, and proving it's real

When the question is whether a *rule or signal* predicts returns (not a single-company read), exploration is cheap and self-deception is easy. Discipline:

- **Start from a mechanism**, not the data. A pattern with no economic reason is probably luck.
- **Test out-of-sample.** Build and tune on one slice; commit to a held-out slice you touch *once*, at the end. That held-out result is the honest one — and only honest if you never peeked.
- **Then apply real statistical rigor — this is where most analysis is too soft:**
  - **Run the factor regression — don't just name it.** Actually regress the return stream on the known factors (market, size, value/HML, profitability, momentum), and report the *residual* alpha with its t-stat plus which factor the return most resembles. "This might be the value factor" is not enough; if factor betas explain the return, it's a factor proxy, not alpha.
  - **Demand a monotonic gradient.** A real ranked signal shows a gradient across deciles (and a long-short spread), not just one lucky top bucket.
  - **Clear a real significance bar, robustly.** Report t-stats with autocorrelation-robust (Newey-West) standard errors and a bootstrap confidence interval — never a bare point estimate. Account for how many things you tried (a hurdle like t > 3 for a "new" effect), and prefer many rolling out-of-sample windows over one lucky split.
  - **Beat the base rate.** Positive return isn't an edge if the asset drifts up anyway — beat the benchmark or majority outcome, out-of-sample.
- **The held-out test is spent once you look at it.** No re-tuning and re-checking against it.

## Signal vs. noise

Most patterns in financial data are noise; with enough looking you'll always find *something*. Before trusting a candidate, pressure-test it: **mechanism** (an economic reason?), **stability** (across time, regimes, names — or one flattering stretch?), **robustness** (survives small changes to window/threshold?), **magnitude** (matters after costs?), **tradability** (actionable, or buried in illiquid names?). These shortlist; they don't prove. The only arbiter is out-of-sample performance — and the more you searched, the more skeptical you should be of any single winner.

## Point-in-time discipline & data traps

Financial data manufactures fake edges. Handle these deliberately:

- **Survivorship bias** — never test on only the names that exist today; include delisted, acquired, and bankrupt ones, or your universe is rigged toward winners.
- **Restatements (point-in-time)** — use the filing version public *as of the decision date*; never let a later amendment (10-K/A) leak backward.
- **Corporate actions** — confirm prices are split- and dividend-adjusted before computing any indicator or ratio.
- **Non-standard fiscal calendars** — a "Q1" can end in almost any month; align fundamentals to the actual filing date, not a fixed calendar month.
- **After-hours / weekend information** — roll its timestamp forward to the next market-open bar (the first moment it was actionable).
- **Outliers & bad prints** — one erroneous datapoint can fake an edge; inspect extremes before trusting them.
- **Insufficient history / regime change** — a signal that works in one short, single-regime window may be noise; relationships decay, so weight recent data and don't assume stationarity.
- **Illiquidity** — an edge in thinly-traded names may vanish after spreads and impact.
- **Misalignment lookahead** — joining on the wrong timestamp (fiscal vs filing date, today's close vs next open) silently leaks the future.
- **Multiple testing** — test many things and some look good by chance; raise the bar accordingly.
- **Missing data** — for a liquid universe this is usually minor; where gaps occur, don't drop rows wholesale (skews toward large-caps) and don't fabricate (mean-fill/interpolation invents signal) — carry the last known value forward, mark genuine unknowns.

## Honesty guardrails

State each once; these separate analysis from storytelling.

- **Tested over asserted.** Conviction, narrative, and a confident tone move nothing — only out-of-sample evidence does. Rank and conclude on what survived a test, never on how sure you feel.
- **Point-in-time, no lookahead.** Use only what was knowable on the decision date.
- **Don't fabricate.** If you lack the data, say so plainly — never invent numbers, tickers, bar counts, or a "data pull" you didn't run to make a point look grounded. "I can't verify this" beats a confident fiction.
- **A faithful "no edge" or "can't tell" is a real result** — and beats a flattering answer built on overfitting, peeking, or invented data.

## Reaching a conclusion

Depth should make you *sharper*, not more hedged. After the work, take a view — proportioned to the evidence: where it leans, your confidence, the 2–3 things that would change your mind, and what to watch next. Don't bury a real conclusion under endless caveats; don't manufacture certainty the evidence doesn't support either.

This is analysis, not personalized advice — render a reasoned view on the asset, but you're not directing someone what to do with their money in their specific situation. Lead with the verdict, state each discipline once, and skip the flourish.
