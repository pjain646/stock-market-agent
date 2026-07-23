# Multi-agent research pipeline — iteration 25

## Analyst team

### Fundamental analyst
Coverage drove the pick. Both inputs are dense — StockholdersEquity 97%, Assets 99% — so the factor is defined across essentially the whole panel, unlike anything I could build on GrossProfit (42%) or CostOfRevenue (25%). I ruled out gross/operating-margin variants for exactly that sparsity, and ruled out accruals/earnings-quality (Sloan) because it needs cash-flow-statement or working-capital deltas that aren't in the concept list — not point-in-time-safe to reconstruct.

### Macro analyst
(no output)

### Sentiment analyst
(no output)

## Proposed factors

- **equity_to_assets_solvency** [fundamental] (data_available=True)
  Within-industry-ranked book solvency, StockholdersEquity / Assets (the low-leverage "safety" leg of Quality-Minus-Junk, balance-sheet flavor). Mechanism: conservatively financed firms carry lower financial-distress and refinancing risk; in the 2022–24 rising-rate regime the market re-priced leverage gradually, so high-equity/low-debt firms earn a slow drift as distress/refinancing premia on levered names unwind. It is a balance-sheet stock (solvency LEVEL), structurally orthogonal to the discipline leg (asset-growth CHANGE) and the profitability legs (income/assets), giving the bundle a genuinely new fundamental dimension rather than another permutation of the exhausted three.

- **usd_broad_dollar_pressure** [macro] (data_available=True)
  A high and rising broad trade-weighted USD (DTWEXBGS) is a tightening of *global* financial conditions and a documented component of every mainstream FCI: it raises the cost of offshore dollar funding, drains global liquidity, and mechanically compresses the translated foreign earnings of large-cap US multinationals. The mechanism is discount-rate/liquidity tightening, same direction as rising yields, so the sign is fixed and cannot flip regime-to-regime: a rapidly strengthening dollar is never a 21-day tailwind for this universe. Its value over the existing rate leg is the risk-off divergence channel — episodes where Treasury yields FALL (bullish per the rate-pressure leg) but the dollar SPIKES on flight-to-safety (bearish), which the DGS10/curve/VIX score alone misprices.


## Bull/bear debate (2 turns)


Bull Researcher: REPORT — Bull, opening

**Both factors clear the two bars that actually matter: a fixed-sign mechanism, and orthogonality to the exhausted three axes. That is exactly what the campaign said it needed — new dimensions, not another leg-swap.**

**1. equity_to_assets_solvency is a genuinely new fundamental axis, not a profitability re-skin.**
The existing fundamental legs are a growth CHANGE (asset growth) and income/assets LEVELS (profitability). Equity/Assets is a *capital-structure level*. Mechanically it can move opposite to profitability: a highly profitable firm can be lowly capitalized (buybacks funded by debt — think levered industrials, or any firm that has returned equity to zero), and a boring low-ROA firm can be near-unlevered. So it does not mechanically inherit the profitability leg's ranks. The QMJ literature treats safety and profitability as *separate* priced components for this reason — they are bundled in the paper precisely because they are not the same signal. On the discipline leg: asset growth is a first difference, solvency is a level; the two are close to orthogonal by construction, which is the analyst's stated intent.

**2. The solvency mechanism is dated correctly for this holdout.** 2022–24 is a rising-rate regime where refinancing and distress premia on levered names repriced *gradually* — that slow repricing is the drift the factor harvests. This is not "low-vol quality always wins"; it is a specific regime claim tied to the rate path the holdout actually sits in. That makes the sign directional and defensible, not fitted.

**3. usd_broad_dollar_pressure earns its place by the divergence channel, not by duplicating the rate leg.** The Bear's obvious shot is "USD is collinear with yields — it's just the rate leg again." Answer: the whole value is in the *residual* after yields. The named case is flight-to-safety episodes where 10Y yields FALL (rate leg flips bullish) while the broad dollar SPIKES on global dollar funding stress (bearish for multinational large-caps via translated earnings + global liquidity drain). In those weeks the rate/curve/VIX score is actively *wrong-signed* for this universe, and DTWEXBGS is the only leg carrying the correct sign. Collinearity in calm regimes is fine — factors are allowed to overlap when nothing is happening; they earn their keep in the tail weeks that decide a 21-day holdout. And the sign genuinely cannot flip: a rapidly strengthening broad dollar is never a tailwind for US multinationals' forward returns. Fixed-sign macro legs are what the rules ask for.

**4. Coverage is a real, not cosmetic, advantage.** StockholdersEquity 97% / Assets 99% means the solvency factor is defined across essentially the whole panel. The rejected margin variants (GrossProfit 42%, CostOfRevenue 25%) would have been half-missing — a factor that is NaN on 60% of rows is a factor whose backtested score is dominated by whichever names happen to report, i.e. exactly the selection-noise the campaign is trying to escape. Dense coverage is what makes the bundle's score trustworthy.

**5. The refusals were correct and strengthen the pick.** The analyst declined Sloan/accruals because reconstructing working-capital deltas point-in-time-safe isn't possible from the concept list. That is the charter's "I cannot build this honestly" working as intended — and it means what remains on the table is the honestly-buildable subset, not a wishlist.

**Where I'll concede ground in advance:** the two factors are only worth *two slots* if they are each orthogonal to the retained legs — Bear should press hardest on whether solvency's P&L is empirically collinear with the profitability leg in the specific 2022–24 defensive-rotation regime, because that is the one place these could double-count. That's the test I'd want the Manager to weigh. But collinearity of P&L is an empirical question for the bundle build, not a reason to refuse to test — and the mechanisms are distinct enough that the prior is orthogonal.

Net: two fixed-sign mechanisms on two axes the bundle doesn't currently span, both densely computable point-in-time. This is the "new axis" the plateau has been waiting for. Worth the iteration.
Bear Researcher: REPORT — Bear, opening

The Bull's framing is that these are "two new axes." Mechanically they are two new *input series* driving **one** bet: monetary tightening rewards defensives. That is the single most dangerous thing you can do on a 2022–24 holdout, and it is dressed up here as diversification.

**1. The two new legs are collinear in realized P&L with the EXISTING rate leg — the cross-axis overlap, not the one the Bull conceded.**
The Bull pre-conceded the solvency-vs-profitability question and told me to press there. Wrong axis. The real collinearity is:
- `equity_to_assets_solvency` = within-industry inverse leverage. Its whole thesis (per the analyst) is that *high-equity/low-debt firms drift up as distress/refinancing premia on levered names unwind in a rising-rate regime.* That is **the same latent driver** as the existing DGS10/curve rate-pressure leg: both pay off precisely when rates rise and rate-sensitive/levered names get punished.
- `usd_broad_dollar_pressure` — the analyst says it outright: *"the mechanism is discount-rate/liquidity tightening, same direction as rising yields."* That is a confession of collinearity with the rate leg, not orthogonality.

So all three — rate leg, solvency, dollar — share one macro factor: tightening → defensives win. The input series are constructed to look orthogonal; their **P&L is not**, in exactly the regime that decides the holdout. This is the charter's named failure: *"their P&L will be collinear in the regime that decides the holdout."* If the 21-day window contains any dovish/risk-on stretch (the 2023 rally, the late-2023 pivot), all three legs miss *together*. Three legs, one bet. (Correlation unmeasured — I'm arguing mechanism, and the mechanism statements are the analyst's own words.)

**2. Most-likely artifact: the dollar leg. It is a single-regime bet with ~1 independent observation.**
DTWEXBGS rose hard through 2022 and stayed elevated. Over a ~2-year, 21-day-forward holdout, the broad dollar delivers effectively *one* big up-cycle — a handful of independent macro episodes, not a repeatable cross-sectional signal. A near-monotone macro level that trended one direction through the window is *indistinguishable from luck* on this sample. That is Campaign-1's exact failure (a noisy signal that fit the validation window) wearing a macro costume. The "high AND rising" wording hides whether this is a slow regime dummy (level) or 21-day dollar momentum (change) — either way it's low-information-count.

**3. The Bull's divergence-channel defense is already covered by VIX.**
The unique-value claim is: flight-to-safety weeks where 10Y *falls* (rate leg flips bullish) but the dollar *spikes* — supposedly the dollar is "the only leg carrying the correct sign." False. Flight-to-safety weeks are *by definition* VIX spikes, and the bundle already has VIX carrying the bearish sign in those exact weeks. So the dollar is not the only correctly-signed leg in the divergence tail — it's redundant with VIX there and redundant with DGS10 everywhere else. The residual it uniquely owns is thin.

**4. Selection pressure: the solvency mechanism is reverse-engineered to the holdout window.**
The Bull praises the factor for being "dated correctly for this holdout — 2022–24 rising-rate regime." Read that again: the mechanism is *conditional on the sample period being rising-rate*. That is not a fixed sign — it is "works while rates rise." The reason it looks good is that we already know 2022–24 was a tightening regime. Fitting a mechanism to the known character of the holdout window is selection pressure by another name, whatever the intent.

**5. A genuine data trap the coverage argument hides: negative book equity.**
`StockholdersEquity` is negative for several of the most shareholder-friendly large caps in this universe (buyback-financed names — HD, MCD, SBUX, AZO-type balance sheets). Equity/Assets goes negative for them, and within-industry ranking then flags the *highest-quality, most cash-generative* firms as maximally "distressed/insolvent." 97% coverage is worthless if the factor is *sign-inverted* on the exact names where capital return has driven book equity below zero. The mechanism (low equity = distress risk) is simply wrong for those firms, and the analyst's coverage-first framing never addressed it.

**Where I give ground:** neither factor has a lookahead leak — filing-date fundamentals and daily FRED series are both point-in-time-safe. And solvency *is* mechanically distinct from the profitability leg, as the Bull argued. Those are real.

**Net for the Manager:** the honest version of this bundle is *one* new fundamental axis (solvency, if the negative-equity handling is specified), **not** two. The dollar leg fails on two counts — it is redundant with both the rate leg (analyst's own "same direction as rising yields") and VIX (the divergence tail), and it is a one-episode macro bet on this window. Adding it doesn't diversify the bundle; it concentrates it further onto the single tightening trade. Drop `usd_broad_dollar_pressure`; make solvency define its treatment of negative book equity before it's built.


## Research manager decision

SELECTED: equity_to_assets_solvency

REASONING:

**What the bear got right — and it's decisive on the macro leg.** The dollar factor dies on a point the analyst handed over for free: "the mechanism is discount-rate/liquidity tightening, same direction as rising yields." That is a confession of collinearity with the existing rate leg, not a second axis. But the killing blow is the external reviewer's, and it is structural, not empirical: `usd_broad_dollar_pressure` is a single time-series value assigned identically to all 166 tickers. In a cross-sectional rank it contributes **zero discriminating information** — it cannot say which stock outperforms, only when the whole tape does. The translation mechanism the analyst leans on (compressed foreign earnings) *requires* a firm-level foreign-revenue or dollar-funding interaction that was never proposed. Without that interaction it is not a factor on this task; it is market timing with an effective sample of roughly one dollar up-cycle over 2022–24. The bear's "three legs, one bet" and "one-episode macro" objections both land, and the reviewer's discrimination point makes them moot anyway. Dropped.

**Why solvency survives.** The bear conceded the two things that matter: no lookahead leak (filing-date fundamentals are PIT-safe), and it is mechanically distinct from the profitability leg (capital-structure LEVEL vs income/assets — a levered high-ROA firm and an unlevered low-ROA firm rank oppositely). Coverage is genuinely dense (97/99%), so its score won't be dominated by whoever happens to report. The bear's real hit — negative book equity on buyback-financed names (HD/MCD/AZO-type) sign-inverting the factor to flag the highest-quality firms as "distressed" — is a **buildability spec, not a kill**. It is binding on implementation: exclude or separately handle negative-equity rows, exclude/segment financials whose leverage accounting differs, apply fixed filing lags and winsorization. Build it that way or not at all.

**Why one factor, explicitly.** The charter is right that a lone factor is the Gate-1 failure shape, and I do not select one lightly. But the only other proposal on the table is not a weak-but-orthogonal cross-sectional factor that would break the best-of-N pattern — it is a universe-constant timing series that carries no cross-sectional rank information at all. Forcing it in to hit a two-slot quota would not diversify the bundle; it would inject pure timing noise and recreate the exact selection-pressure hazard (an underspecified market-timing leg fitted to a known-tightening window) the reviewer warned against. A second axis that cannot discriminate stocks cannot serve the anti-selection purpose that justifies bundling. This iteration failed to produce a second *buildable, cross-sectional* orthogonal axis. The correct response is to ship the one honest factor preregistered — not to pad. The macro analyst should return next iteration with a dollar factor interacted with firm-level foreign-revenue exposure and an explicit level-vs-change definition; that would be a real second axis.


## Selected factors
equity_to_assets_solvency
