# Multi-agent research pipeline — iteration 34

## Analyst team

### Fundamental analyst
(no output)

### Valuation analyst
(no output)

### Macro analyst
I am proposing the proven leg, not a new permutation, and the genuinely-new argument the manager has not yet heard is empirical: **the last two iterations dropped this macro leg and both failed — iter 32 (−0.0108) and iter 33 (−0.0037).** That is not coincidence; it is the mechanism's prediction confirmed out-of-sample. Both dead bundles paired two slow-moving cross-sectional value/quality ratios (ρ≈0.01, genuinely orthogonal in *construction*) that nonetheless shared one regime exposure — fundamental value bleeds down when rates rise — so they reinforced a single losing tilt with no orthogonal timing axis to diversify it. The macro TIMING leg is the ONLY axis in the campaign whose sign is stable across the 2022–2024 rate-up window and whose P&L is orthogonal to a value/quality tilt by *mechanism*, not just by correlation. Removing it removed the diversifier and the bundle collapsed to a one-directional bet — twice.

### Sentiment analyst
(no output)

## Proposed factors

- **deleveraging_momentum** [fundamental] (data_available=True)
  This is the CHANGE analogue of the campaign's most-validated fundamental — the equity-to-assets solvency LEVEL (iters 25/29/30/31, +0.0751). The mechanism is balance-sheet repair: a firm whose book-equity/total-assets ratio is *rising* year-over-year is retaining earnings, paying down debt, or de-risking its asset base, which lowers prospective distress risk. The distress anomaly says the market underreacts to the *trajectory* of financial-health improvement — it prices the current level but is slow to re-rate the trend — so deleveraging firms out-drift over the next 21 days. It is a capital-structure FLOW axis, orthogonal by construction to both the solvency LEVEL (Δ vs. level of the same ratio) and to ROA-change profmom (capital-structure change vs. earnings change).

- **book_to_market_within_sector** [valuation] (data_available=True)
  Book-to-market is the canonical HML value measure (Fama-French): firms priced cheaply relative to the accounting value of their equity earn a persistent risk/reversal premium as over-extrapolated pessimism corrects. Its mechanism is genuinely distinct from the earnings-yield leg tested in iter 21/22: B/M is anchored to a *balance-sheet stock* (equity), not an *earnings flow*, so it does not blow up or flip sign when a firm posts a transitory near-zero or negative net income year — it captures deep-value/distress-reversal names that earnings yield misclassifies. Ranked *within sector* (sector-demeaned) so the well-known structural tilt (tech/CommServices always "expensive," Financials/Utilities always "cheap") is removed and the factor discriminates cheap-vs-expensive *among peers* rather than just reprinting the sector map.

- **duration_scaled_rate_pressure_timer** [macro] (data_available=True)
  High/rising Treasury yields raise discount rates — a pooled-NEGATIVE, sign-stable headwind for this large-cap universe in every sector (confirmed iter 16/17), never a regime-dependent sign flip. A composite bullish-conditions score (low/falling DGS10, steeper T10Y2Y, elevated VIXCLS risk premium) is scaled by a coarse 3-level industry cash-flow-duration weight (Tech≫Fin>Pharma-defensive) so the same-signed macro headwind becomes a CROSS-SECTIONAL ranking signal — it times WHEN the tape moves and duration decides WHICH names lead. This is the exact macro TIMING leg that carried the +0.0751 solvency_profmom_macro bundle (iters 25/29/30/31) and scored +0.0521 standalone.


## Bull/bear debate (2 turns)


Bull Researcher: ## Bull case — open

This bundle clears the bar the charter actually sets: **two legs that can genuinely rank stocks on different axes, plus a timing leg that is orthogonal by mechanism.** That is exactly the structure iters 32/33 lacked and paid for.

**1. The two cross-sectional legs are orthogonal in construction, not just in a fitted ρ.**

- `deleveraging_momentum` is a capital-structure **flow** — the YoY *change* in equity/assets. `book_to_market_within_sector` is a valuation **stock** — the *level* of equity relative to price, sector-demeaned. One asks "is this firm's balance sheet *improving*," the other asks "is this firm *cheap* relative to its book." A firm can be deleveraging while expensive (quality compounder repaying debt) or cheap while re-levering (distressed value trap). The 2×2 is populated in all four quadrants, which is the definition of an orthogonal pair — they disagree on real names, not just on average.
- Critically, `deleveraging_momentum` is the **Δ** of the campaign's most-validated fundamental (equity/assets level, +0.0751), *not the level itself*. That is the orthogonality that matters: it does not re-print the solvency LEVEL leg, it captures the trajectory the market re-rates slowly. The distress-underreaction mechanism is well-grounded — the market prices the current health level but lags the trend.

**2. B/M is the right second value axis precisely because it is NOT earnings yield.** Iters 21/22 tested earnings yield, an *earnings flow* that flips sign or blows up on a transitory near-zero/negative-income year. B/M is anchored to a balance-sheet stock, so it stays well-defined through exactly those firms — the deep-value/distress-reversal names earnings yield misclassifies. Sector-demeaning removes the structural "tech always expensive / utilities always cheap" tilt, so the leg discriminates among peers instead of reprinting the sector map. This is the standard rescue for HML and it is the correct one.

**3. The macro leg's case is now empirical, and that is the strongest part.** The charter is right that a macro factor cannot *rank* stocks alone — but this leg is duration-*scaled*, so the same-signed rate headwind becomes a cross-sectional weight (Tech ≫ Fin > defensives). More importantly, we have the counterfactual the team usually lacks: **the last two iterations dropped this exact leg and both went negative (−0.0108, −0.0037).** Those bundles paired two slow value/quality ratios that were orthogonal in construction (ρ≈0.01) yet shared one regime exposure — value bleeds when rates rise — so they were a single-directional bet dressed as a diversified one. The macro timer is the only axis whose sign is stable across the 2022–2024 rate-up window *and* whose P&L is orthogonal to a value tilt by mechanism. It is the diversifier that was removed when the bundle collapsed. It also has standalone evidence (+0.0521) and carried the +0.0751 bundle across iters 25/29/30/31.

**Where the bear should aim, so we don't waste the round:** the honest soft spot is not orthogonality — it's whether `deleveraging_momentum` and `book_to_market` *both* quietly load on the same rate-sensitive-value tilt that killed 32/33, in which case the macro leg is diversifying against a doubled-up exposure and we're back to a one-axis bet plus a timer. That is the real question, and it's answerable in-test. But the bundle is built to survive it: the fundamental leg is a **flow** and B/M is sector-demeaned, both of which cut the shared rate-beta the two dead bundles carried. This is worth the iteration — it is not another permutation of exhausted axes, it is the one configuration the last two failures actively predict should work.
Bear Researcher: ## Bear case — where this fails out-of-sample

The Bull told me to aim at whether the two cross-sectional legs double up. I'll take that, but the bigger problem is upstream: **two of the three legs are here because they already scored well, and that is the Campaign-1 failure mode by name.**

**1. This bundle is fit to the validation history — the exact selection pressure the charter warns about.** Read the justifications literally. The macro leg is defended as "the *exact* macro TIMING leg that carried the +0.0751 solvency bundle (iters 25/29/30/31)" and "scored +0.0521 standalone." The fundamental leg is defended as "the CHANGE analogue of the campaign's *most-validated* fundamental (+0.0751)." Neither is argued from a fresh mechanism the team hasn't already leaned on — both are argued from *prior scores*. That is keeping-the-best-of-N wearing a bundle costume. Campaign 1 scored +0.0521 on validation and **−0.0118 on holdout** from precisely this reasoning. The macro timer's standalone +0.0521 is the *same magnitude* as that artifact. "It carried the good bundle before" is not a mechanism; it is the thing the holdout exists to punish.

**2. The two cross-sectional legs share a book-equity-accretion driver — the doubling-up the Bull flagged and then waved off.** `deleveraging_momentum` is Δ(book-equity/assets); `book_to_market` is book-equity/price. **Retained earnings raises book equity in both numerators simultaneously** — a firm that retains earnings looks like it's "deleveraging" (E/A up) *and* like it's "getting cheaper on book" (B/M up) from the identical accounting event. The "flow vs. stock" distinction the Bull leans on is cosmetic when the common input is book-equity growth. This is unmeasured, but the mechanism predicts *positive* coupling, not the orthogonal 2×2 the Bull asserts. If they co-load, we are back to a single value/quality tilt — the one-directional bet that bled in 32/33 — and the macro leg is diversifying a *doubled* exposure, not two independent ones. The Bull conceded this is "the real question" and then answered it with "the fundamental leg is a flow and B/M is sector-demeaned, both of which cut the shared rate-beta." Sector-demeaning removes the *sector* tilt; it does nothing to the *book-equity-growth* shared driver, which is a firm-level, within-sector effect. The rebuttal misses the channel.

**3. The macro leg embeds exactly the tuning the ablation told us to distrust.** It is "scaled by a coarse 3-level industry cash-flow-duration weight (Tech≫Fin>Pharma-defensive)." That is a hand-set per-industry weight vector. The campaign already found ~27% of the best bundle's score was tuning-attributable, and removing hand-set per-sector weights took +0.0654 → +0.0476. The duration weights are that suspect component. Strip them and the "same-signed macro headwind" is one number per date shared by all 166 tickers — which the charter (Codex iter 25) established **contributes zero cross-sectional ranking information.** So the macro leg's ability to *rank* rests entirely on the 3-level weight the ablation flagged, not on the rate signal itself.

**4. Point-in-time and staleness flags on `deleveraging_momentum`.** YoY Δ(E/A) requires *two* annual filings, and the year-ago value must be the number known as-of the year-ago filing date — **not** a later-restated figure. If the pipeline pulls the year-ago equity/assets from the current database state, it silently uses restated balance-sheet data = lookahead. This is answerable but must be verified, not assumed. Separately: an annual-filing Δ is near-static across a 21-day horizon and only updates once a year, so for most rows it's a stale constant — thin, low-turnover signal to hang a "flow axis" on.

**What would change my mind:** a measured within-sector correlation between `deleveraging_momentum` and `book_to_market` near zero (killing objection 2), and an ablation showing the macro leg adds rank information with the duration weights *flattened* (killing objection 3). Absent those, this is the +0.0751 recipe re-plated — and the plateau at +0.057–0.065 across leg-swaps says re-plating doesn't move the holdout.


## Research manager decision

SELECTED: book_to_market_within_sector, deleveraging_momentum

REASONING:

**What the bear got right — and it was decisive on the macro leg.** The macro
timer is dropped. Three things converged against it:

1. Its one genuinely new argument — "iters 32/33 failed without it, so removing
the diversifier caused the collapse" — was correctly dismantled by the external
reviewer. Those iterations were adaptively observed, changed multiple legs at
once, and had no controlled with/without-macro comparison. You cannot causally
attribute two failures to the removal of one leg. Strip that argument and the
macro case reduces to "it scored +0.0521 standalone and carried the +0.0751
bundle" — which is reasoning *from prior scores*, i.e. the exact selection
pressure that took Campaign 1 from +0.0521 validation to −0.0118 holdout.
2. The charter (Codex iter 25) already established a pooled macro number ranks
zero cross-sectionally. This leg's *only* ranking content is the coarse 3-level
hand-set duration weight — and the ablation told us hand-set per-industry
weights are the suspect, tuning-attributable component (+0.0654 → +0.0476). So
the leg's discriminating power rests entirely on the piece we distrust most.
3. The reviewer's date-clustering point compounds it: one value per date means a
far smaller effective sample than the row count implies, inflating apparent
robustness. The macro leg is the most likely artifact in the bundle. It goes.

**Why not fundamental+macro instead:** even setting the above aside, the charter
is explicit that a value leg plus a macro timer is not two real cross-sectional
axes — the macro leg times, it doesn't rank. Keeping it would leave one ranking
axis dressed as two.

**Why the remaining two survive as a pair.** The bear's strongest cross-sectional
objection — that `deleveraging_momentum` (Δ book-equity/assets) and
`book_to_market` (book-equity/price) share a book-equity-accretion driver — is a
real, correctly-identified coupling channel, and I credit it. But it is
*predicted, not measured*, and it is partial: one is a YoY **change** gated by
debt and asset dynamics, the other a **level** dominated by price. Changes and
levels of related quantities are typically weakly correlated, and the value-trap
quadrant (cheap on book while re-levering) is real and populated. These are two
different mechanisms — trajectory of balance-sheet repair vs. cheapness on book —
not one restated twice. That is a genuine two-axis cross-sectional bundle, which
is what breaks the best-of-N pattern; a lone factor would not.

**Two binding conditions on the build (both from the bear, both valid):**
- `deleveraging_momentum` must pull the year-ago equity/assets as the figure
  known **as of the year-ago filing date**, never a later-restated value. If the
  pipeline reads current-database balance-sheet state for the prior year, that is
  lookahead and the leg is disqualified.
- Measure the within-sector correlation between the two legs before trusting the
  result. If it comes back materially positive, the bear's coupling objection is
  confirmed and this collapses toward a one-directional value tilt — flag it
  loudly rather than reporting a clean two-factor score.

Two orthogonal-by-mechanism cross-sectional legs, the tuning-dependent
artifact-prone macro leg removed. That is the bundle.


## Selected factors
book_to_market_within_sector, deleveraging_momentum
