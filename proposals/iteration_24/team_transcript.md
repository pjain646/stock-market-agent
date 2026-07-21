# Multi-agent research pipeline — iteration 24

## Analyst team

### Fundamental analyst
Choosing what the journal has NOT isolated. Gross profitability has appeared in this campaign only once — buried as one leg (`cd_gp_to_assets`) inside the iter-7 capital-discipline/quality composite, which was scored as an 8-feature tree bundle and never let this leg speak on its own. It has never been proposed as a standalone factor. That matters because Novy-Marx's central empirical claim is that gross-profits-to-assets has roughly the same predictive power as book-to-market yet is *negatively* correlated with it, so it is a distinct axis, not a re-packaging of the value (earnings-yield) leg that already worked in iters 21–22.

### Macro analyst
Task brief says macro timing is the strongest axis but concentrated in rate-coupled sectors, and that sign-STABLE conditions generalize while regime-dependent sign flips do not — so I looked for a genuinely new, sign-stable financial-conditions channel that is (a) NOT the rate/curve/VIX levels already saturated in iters 13/16/17/20, and (b) plausibly broader than rates.

### Sentiment analyst
I own the sentiment axis, and the faithful conclusion is that it cannot be built point-in-time-safe here — same wall iteration 23 hit, and I will not paper over it with a proxy.

## Proposed factors

- **gross_profitability_ind_rank** [fundamental] (data_available=True)
  Gross profits-to-assets (revenue − COGS, over total assets) is the cleanest point on the income statement for measuring true economic productivity — it sits above SG&A, R&D, depreciation, interest and tax, so it is not contaminated by the accounting choices and discretionary long-run investments that muddy net income and even operating income (Novy-Marx). The market anchors on bottom-line EPS and systematically underweights high-gross-profitability firms, which are productive assets trading cheap; they subsequently out-drift. Ranked within industry because gross-margin structure differs enormously across the 11 sectors (software vs. retail vs. banks), so only the industry-relative level isolates the productivity signal rather than a sector fixed effect.

- **credit_spread_momentum** [macro] (data_available=True)
  The Moody's Baa–Aaa corporate credit spread is a real-time market gauge of the aggregate default/risk premium and corporate funding conditions. Its 21-day *direction of change* (momentum), not its level, is the sign-stable channel: when the spread is tightening, the marginal cost of corporate capital is falling and risk appetite is broadening, a market-wide tailwind subsequently earned across equities; when it is widening, funding stress presages drawdowns. Because it captures the *flow* of conditions rather than the absolute level, its sign holds across both the low-rate training era and the 2022–2024 tightening cycle, and because credit conditions raise/lower every firm's cost of capital it should broaden macro breadth beyond the purely rate-coupled sectors.

- **analyst_grade_narrative_sentiment** [sentiment] (data_available=False)
  The genuine sentiment mechanism I want is investor-narrative revision — when brokers/news reprice a name (upgrades, positive coverage, rising confidence), retail and slow institutions chase the revised narrative and price drifts in that direction over ~1 month (belief-updating underreaction). Quantifying it honestly requires a source that records, with a real publication timestamp, what was public sentiment on each row's date. No such source is wired up in this environment.


## Bull/bear debate (2 turns)


Bull Researcher: # BULL CASE: Test this bundle.

The bundle is really two live factors plus one honest abstention. I'll defend the two that matter and refuse to inflate the third.

## 1. Gross profitability is genuinely un-tested here, and orthogonal to the value leg that already worked

The bear's easiest shot is: "iters 21–22 already won on earnings-yield; this is just value warmed over." That's wrong on the arithmetic, and Novy-Marx handed us the disconfirming test before the bear can raise it.

- **Gross profits-to-assets is *negatively* correlated with book-to-market.** High-GP firms are the productive, high-margin names that value screens actively *reject* as too expensive. If this were a repackaging of the earnings-yield leg, the two would be positively correlated and GP would add nothing incremental. The literature's central finding is the opposite: comparable predictive power, opposite tilt. That is the definition of an orthogonal axis, and it's directly falsifiable in-sample — **we can measure the rank correlation between `gross_profitability_ind_rank` and the iter-21/22 value signal before committing a full iteration.** If |ρ| > ~0.4, I fold. I expect it near zero or negative.

- **It has never spoken on its own.** The one prior appearance was `cd_gp_to_assets` as 1 of 8 legs in an iter-7 tree bundle. An 8-feature tree cannot tell you whether GP carries signal — its marginal contribution was never isolated, and tree bundles bury linear monotone signals under interaction noise. "Appeared once, buried, in a composite" is not "tested." This is a clean standalone test of a factor with one of the strongest out-of-sample track records in the cross-sectional literature.

- **The mechanism is above-the-line, which is the whole point.** Revenue − COGS sits above SG&A, R&D, depreciation, interest, tax. Every one of those lines is where accounting discretion and long-horizon investment *depress reported net income for economically strong firms*. That's precisely why the market, anchoring on EPS, misprices them. The mispricing mechanism and the "cleanest productivity measure" mechanism are the same mechanism — that coherence is what you want in a factor.

- **Industry-rank is the correct construction, not a hedge.** Software runs 80% gross margin, grocery runs 25%. A raw GP screen is a sector bet. Ranking within industry strips the sector fixed effect and isolates the *within-peer* productivity signal — which is the drift-generating variable.

## 2. Credit-spread momentum is a new, sign-stable macro channel — not the rate/curve/VIX levels already saturated

The bear will say "iters 13/16/17/20 already saturated macro; this is another rates proxy." Two concrete rebuttals:

- **It's a change, not a level, and it's not rates.** Prior macro legs were *levels* of rate/curve/VIX. This is the *21-day direction of change* of the Baa–Aaa spread. Level factors and momentum-of-a-different-series factors are close to orthogonal by construction. Baa–Aaa is a pure *credit-risk premium* spread (two corporate grades) — it nets out the Treasury/rate component entirely. So it is neither a rate level nor a rate change. It's the default/risk-appetite channel, which is exactly the "broader than rates" axis the macro brief asked for.

- **Sign-stability is the survival criterion, and this passes it mechanically.** The brief's rule: sign-stable channels generalize, regime-dependent sign flips don't. Spread *tightening* = falling marginal cost of corporate capital + broadening risk appetite = tailwind. Spread *widening* = funding stress = drawdown. That sign does **not** flip between the low-rate training era and the 2022–2024 tightening cycle — widening spreads meant stress in *both* regimes. Contrast with rate *levels*, whose equity sign is regime-dependent (rising rates helped in reflation, hurt in 2022). This is why the change-of-credit-conditions is a better generalizer than the rate levels already in the book. **Testable directly: estimate the sign in the pre-2022 and 2022–2024 subsamples separately; if the sign flips, it fails the brief's own rule and I drop it.**

- **Breadth.** Credit conditions move *every* firm's cost of capital, not just rate-coupled sectors. If the macro axis's weakness so far is concentration in rate-sensitive sectors, a credit channel is the natural breadth-diversifier.

## 3. On the sentiment leg — I am *with* the sentiment analyst, and that strengthens the bundle

I will not defend `analyst_grade_narrative_sentiment`. `data_available=False`. There is no point-in-time-safe source with real publication timestamps; iter-23 hit the same wall. Building a proxy would inject lookahead and poison the whole iteration's read. **Drop it from the test entirely.** The honest bundle is two factors. That we're *refusing* the unbuildable leg rather than papering it with a proxy is exactly why you should trust the two we are proposing.

## Why it's worth the iteration

- Two orthogonal axes (a cross-sectional fundamental + a macro conditions channel), each with a pre-registered falsification test we can run cheaply *before* the full evaluation: GP's correlation vs. the value leg, and credit-momentum's sign-stability across the 2022 break.
- Neither has been isolated in this campaign. GP is the single most-cited profitability factor in the literature and has never spoken alone. Credit-spread momentum is a level-orthogonal, rate-orthogonal, sign-stable channel that directly targets the macro axis's known weakness (sector concentration).
- The downside is bounded: two clean, interpretable, point-in-time-safe features with real mechanisms. If either fails its pre-registered check, we cut it. That's a cheap, high-information iteration — not a fishing trip.

Bear: your strongest line is redundancy. I've named the exact statistic that settles it for each factor. Bring the correlation numbers, not the intuition.
Bear Researcher: # BEAR CASE: This bundle fails out-of-sample on the macro leg, and the fundamental leg is testing the wrong redundancy.

The bull did something clever: he pre-registered two falsification tests, named the statistics, and dared me to "bring the numbers." But look at *which* tests he chose. For each factor he picked the redundancy check he wins and quietly avoided the one he loses. That is selection pressure operating on the *argument itself*. Let me route around his framing.

---

## 1. `credit_spread_momentum` is a scalar-per-date overlay — the single highest-variance-of-estimate object you can put in a cross-sectional bundle

This is the leg that kills the holdout. Concrete, not intuition:

**It carries zero cross-sectional information.** On any given date, Baa–Aaa spread momentum is *one number* applied identically to every name in the universe. It cannot rank AAPL vs MSFT. Its *only* channel to alpha is timing gross/net exposure across time. So its entire contribution is estimated from the number of **independent time-series observations**, not from N×T stock-days. A 21-day momentum of a slow, autocorrelated macro series over a ~2015–2024 training window gives you on the order of **10–40 genuinely independent regime observations**. You are fitting a sign (and, once it's in a bundle, an implicit weight) to a couple dozen data points.

That is *exactly* the object that produced this project's first-campaign collapse: +0.0521 validation → **−0.0118 holdout**, and the ablation showing 27% of the current best came from per-sector weights A/B-tested against validation. A macro overlay with ~20 effective degrees of freedom is the same failure mode in a new costume. The bull's "downside is bounded, it's a clean interpretable feature" claim is false for a timing overlay — the variance of its Sharpe *estimate* is enormous precisely because it interpretable and low-dimensional.

**The sign-stability argument confounds contemporaneous with predictive.** The bull's mechanism — "widening = funding stress = drawdown" — is a statement about *contemporaneous* co-movement. Widening spreads and falling equities happen on the *same day*; that is true, well known, and **useless** for a factor that must predict *forward* returns from information at date t. The actual claim being tested is "the last 21 days of spread *direction* predicts the *next* month of returns." That is a momentum-of-a-macro-series claim, and macro spreads mean-revert as often as they trend. The sign of *that* relationship is not mechanically stable — it flips with horizon and regime. The bull asserts stability across the 2022 break; he has not shown it, and his own pre-registered test ("estimate the sign pre/post-2022") is run on the *same data he's selecting on*, so passing it proves nothing about the holdout.

**The redundancy test he named is the wrong one.** He pre-registered orthogonality vs *rate levels* (iters 13/16/17/20) and vs the Treasury component. Fine — and irrelevant. Baa–Aaa *change* is contemporaneously near-collinear with **VIX changes and the market's own return**. It is a risk-off proxy. The existing macro/VIX legs already own the risk-appetite axis. So to the question *"are two of these the same axis wearing different names?"* — yes: `credit_spread_momentum` is the *same risk-off timing axis* as the deployed VIX overlay, differenced from a different series. He tested against the one series it's provably distinct from (rates) and skipped the one it's collinear with (VIX/equity vol). **Bring the ρ vs ΔVIX and vs the market return, not vs rate levels.**

Verdict on this leg: **reject.** Not because the mechanism is wrong contemporaneously, but because as a forward-predictive scalar-per-date overlay it is under-identified and redundant with an axis already in the book.

---

## 2. `gross_profitability_ind_rank` — the bull is testing orthogonality against the value leg because he'd *lose* the test against the quality composite that already contains this exact quantity

Read the fundamental analyst's own report: gross-profits-to-assets already appeared in this campaign as **`cd_gp_to_assets`**, a leg of the iter-7 capital-discipline/quality composite. The bull's entire orthogonality argument is "GP is negatively correlated with book-to-market, so it's not the value leg." **Correct and beside the point.** Nobody's serious worry is that GP duplicates value. The worry is that GP duplicates the *quality/capital-discipline composite that already holds gp_to_assets by name*.

- If that iter-7 composite is part of the current best bundle, then GP's marginal contribution has *already been partially harvested*, and the standalone add is small — while the standalone *estimate* looks large on validation precisely because it correlates with something that already works. That's the selection-pressure trap, direction #3.
- The bull calls the prior appearance "buried… never let it speak on its own." That's rhetoric. "Buried in a composite" doesn't mean "orthogonal to the composite." **The pre-registered test that actually matters: ρ(gross_profitability_ind_rank, iter-7 quality composite score) and the marginal IC of GP *after* residualizing on that composite.** He offered ρ vs the value leg — the one comparison he's guaranteed to win — and stayed silent on the one comparison that could sink the factor. Name-swapping "isolated standalone factor" onto a quantity the campaign already uses is the definition of the same-axis-different-name failure.

I'll concede: GP is the more defensible of the two, its mechanism is coherent and above-the-line, and it deserves a test. But not against the strawman he chose.

---

## 3. Point-in-time / lookahead — `data_available=True` is not `point_in_time=True`

Direction #4, and it applies to the *fundamental* leg, not the macro one:

- Gross profitability needs revenue, COGS, and total assets from financial statements. The silent lookahead is fiscal-period-end vs **filing date**. If GP for a row dated t uses the fiscal quarter that *ended* before t but *filed* weeks after t, the feature uses information not public at the row's date. This is the single most common way profitability factors post fake in-sample alpha. `data_available=True` tells us the columns exist; it says nothing about report-date lagging.
- **Industry-rank compounds it.** Ranking within industry on date t requires every peer's GP as-of t. If even a subset of peers are ranked on not-yet-filed statements, the *rank* is contaminated for the whole sector. Also confirm the industry classification is point-in-time (sectors get reassigned; a backfilled GICS/SIC mapping is itself lookahead).
- Universe-size caveat: Novy-Marx's OOS strength is on thousands of names. If this universe is a few hundred, within-industry deciles are a handful of names each — thin spreads, noisy ranks, and the literature's effect size does not transfer.

---

## What I'd actually accept

- **Drop `credit_spread_momentum`.** Under-identified scalar overlay (~tens of effective obs), contemporaneous-vs-predictive confound, redundant with the existing VIX/risk-off axis. This is the leg most likely to be a validation artifact and the most likely single cause of a holdout collapse.
- **Test GP only if** (a) it's residualized against the iter-7 quality composite, not just book-to-market, and shows marginal IC there; and (b) it passes a strict report-date-lagged, point-in-time industry rank. Pass both and it's a real, orthogonal fundamental axis. Skip either and it's the quality composite wearing a new name.

Bull: you named the statistics that let you win. I'm naming the two that decide it — **ρ(credit momentum, ΔVIX / market return)** and **marginal IC of GP after residualizing on the iter-7 quality composite, on report-date-lagged data.** Bring *those*.


## Research manager decision

SELECTED: gross_profitability_ind_rank

REASONING: One factor, tested properly, beats two where one is a known artifact. The bear won the macro leg decisively and I'm cutting it.

**Why `credit_spread_momentum` is dropped.** The bear's identification argument is fatal and the bull never answered it. Baa–Aaa spread momentum is a scalar-per-date overlay: one number applied identically to every name, carrying zero cross-sectional information. Its entire alpha channel is time-series timing, so it's estimated from ~tens of independent regime observations of a slow, autocorrelated series — not N×T stock-days. That is precisely the low-dimensional timing-overlay object that produced this campaign's documented +0.0521 val → −0.0118 holdout collapse and the per-sector-weight overfit. Two further kills: (1) the bull's "widening = drawdown" mechanism is *contemporaneous* co-movement, which is useless for a factor that must predict *forward* returns from date-t information; the actual claim — 21-day spread direction predicts next-month returns — is a macro-momentum bet whose sign is not mechanically stable and mean-reverts by horizon/regime. (2) The bull pre-registered orthogonality vs *rate levels* — the test he wins — and dodged the one that sinks it: ρ vs ΔVIX / market return. Baa–Aaa change is a risk-off proxy near-collinear with the VIX/vol axis already deployed. Same axis, different series. Reject.

**Why `gross_profitability_ind_rank` survives — conditionally.** It's the more defensible leg: coherent above-the-line mechanism, genuinely never isolated standalone, and one of the strongest OOS factors in the literature. But the bear was right that the bull tested the wrong redundancy. Orthogonality vs the value/earnings-yield leg (negative ρ with book-to-market) is real but beside the point — nobody feared GP duplicates value. The live risk is duplication of the **iter-7 capital-discipline/quality composite that already contains `cd_gp_to_assets` by name.** So this factor goes in with two mandatory pre-evaluation gates:
1. **Residualize on the iter-7 quality composite**, not book-to-market. Require material marginal IC *after* residualizing. If the composite is in the current best bundle and GP's marginal IC collapses, drop it — the signal is already harvested.
2. **Strict report-date-lagged point-in-time construction.** GP must use fiscal periods with a *filing date* ≤ row date, and the within-industry rank must be built only from peers whose statements were public as-of t. Confirm the industry/GICS mapping is itself point-in-time, not backfilled. `data_available=True` ≠ `point_in_time=True`.

If GP clears both gates, it's a real orthogonal fundamental axis worth the iteration on its own. If it fails either, this iteration correctly returns zero new factors rather than a repackaged one.

**Sentiment:** correctly abstained. `data_available=False`, no point-in-time source with real publication timestamps. A proxy would inject lookahead and poison the read — the analyst's refusal is the right call, and I back it.

Shipping one clean, gated factor over a padded bundle.


## Selected factors
gross_profitability_ind_rank
