# Multi-agent research pipeline — iteration 28

## Analyst team

### Fundamental analyst
(no output)

### Macro analyst
(no output)

### Sentiment analyst
(no output)

## Proposed factors

- **operating_profitability_rmw** [fundamental] (data_available=True)
  Operating income per dollar of total assets is the Fama-French RMW / Ball-Novy-Marx operating-profitability anomaly: robustly profitable firms earn higher forward returns because the price-fixated market underweights sustained operating efficiency. Operating income is a cleaner economic-profit measure than net income (strips non-operating items, tax, and one-offs) and more complete than gross profit (nets out the SG&A/overhead the market actually prices), so it captures the productive-quality trait at the operating line. Ranked within (date, industry) so bank/utility margin structures don't dominate the cross-section.

- **vix_riskpremium_scaled_beta** [macro] (data_available=True)
  Conditional risk-premium / time-varying beta anomaly. The compensation for bearing systematic risk is not constant — it fattens when aggregate risk aversion is high (elevated VIX) and thins when it is low. Over a 21-day forward horizon the vol risk premium is one of the most sign-stable macro facts we have, and iter 16 already committed the campaign to the "elevated VIX = bullish forward return" sign and it held in all three sectors. Scaling that sign-fixed risk-premium gauge by each name's trailing market-beta MAGNITUDE (sign pinned positive, cannot invert) means high-beta names get the largest bullish tilt precisely when the premium they earn is fattest — a cross-sectional differentiator that operates every rebalance, not just at the ~3–5 vol spikes.


## Bull/bear debate (2 turns)


Bull Researcher: ## BULL — opening case

**The orthogonality is structural, not hoped-for.** This is the strongest thing the bundle has going for it. `operating_profitability_rmw` sorts the cross-section toward stable, high-margin, capital-efficient firms — and those firms are empirically **low-beta**. `vix_riskpremium_scaled_beta` tilts by trailing **beta magnitude** — it concentrates weight in high-beta names. The two legs load on opposite ends of the beta distribution. Their P&L cannot be collinear the way two rate-sensitive-defensive legs were in prior iterations; if anything the fundamental leg is a natural hedge on the macro leg's beta exposure. That is exactly the property the bundle design exists to buy, and here we get it from the mechanics rather than by luck.

**Both mechanisms are named and independently established — neither is pattern-first.**
- RMW / Novy-Marx operating profitability is a published, replicated anomaly with a real mechanism: the market underweights *sustained* operating efficiency because it fixates on headline earnings. Using operating income (not net income, not gross profit) is the correct level — it strips tax/one-offs the market ignores *and* nets the SG&A the market actually prices. Ranked within (date, industry) so bank/utility margin structures don't hijack the sort.
- The conditional risk premium is ICAPM-standard: compensation for systematic risk is time-varying and fattens with aggregate risk aversion. The vol risk premium's forward sign is one of the most sign-stable macro facts we have, and iter 16 already committed the campaign to "elevated VIX = bullish forward" — and it held in **all three sectors**. This leg doesn't re-open that sign; it pins it positive and only scales the magnitude.

**Preempting the bear's four likely shots:**

1. *"VIX×beta is just the low-vol anomaly wearing a disguise / a bet on beta."* No — the sign is pinned positive by out-of-sample sector evidence and **cannot invert** (magnitude scaling only). It says high-beta names should earn the *most* when the premium is *fattest*. That's the risk-premium mechanism operating as designed, not an un-anchored beta bet.

2. *"It only fires at the 3–5 vol spikes, so it's near-constant dead weight."* The VIX level modulates the tilt, but the **beta-magnitude cross-section differentiates names every single rebalance**. It is not a rare-event switch; it's a continuous cross-sectional gauge that steepens in stress.

3. *"Profitability overlaps a prior quality leg."* It's specifically the *operating* line — orthogonal to gross-profit and net-income constructions by definition, and profitability is a distinct axis from the value/momentum/rate legs the campaign has been permuting. This is a genuinely **new axis**, which is precisely what the plateau at +0.057–0.065 calls for.

4. *"27% of the last bundle was tuning-attributable — beware."* That warning was about hand-set per-sector weights. **Neither leg here has per-sector parameters.** One is a within-industry rank; the other is a sign-fixed scalar times a beta magnitude. This bundle is parameter-light by construction, which directly answers the tuning-inflation lesson rather than repeating it.

**Why it's worth the iteration:** two orthogonal legs, two established mechanisms, no per-sector tuning surface, and — critically — a *new* fundamental axis plus a cross-sectional upgrade to a previously binary macro signal. That combination is more likely to move off the plateau than another permutation of the exhausted three axes.

Two honest checks I'd hand the bear rather than paper over: (a) both flag `data_available=True`, but the profitability leg lives or dies on operating income being stamped **by filing date, point-in-time** — confirm that, not fiscal-period end; (b) the macro leg's per-name **trailing beta must be estimated on a strictly backward window**. Neither is fatal; both are verifiable. Bear — your move.
Bear Researcher: ## BEAR — this bundle's "orthogonality" is its fatal flaw, not its feature

**1. The two legs are not orthogonal — they are a straddle on ONE axis: beta.**

The Bull's central claim is that `operating_profitability_rmw` (low-beta names) and `vix_riskpremium_scaled_beta` (high-beta names) "load on opposite ends of the beta distribution" and therefore "cannot be collinear." Read that again — *opposite ends of the same axis is not orthogonality, it is anti-correlation on a single factor.* Two legs that pull in opposite directions along beta are perfectly *dependent*; they just have opposite sign.

Here is why that kills the diversification story. Over a 21-day horizon, whichever way the beta factor pays in the holdout window becomes the dominant PnL driver for *both* legs simultaneously:
- Risk-off holdout (beta pays negative): profitability leg wins, VIX×beta leg loses.
- Risk-on holdout (beta pays positive): reverse.

So the bundle's score largely collapses to **the sign of a single beta bet in the sealed window** — high variance, regime-determined, exactly the concentrated single-axis exposure the bundle design exists to avoid. This is the collinearity failure mode wearing a costume, not a cure for it. (Correlation unmeasured — but the *mechanism* forces the dependence; you don't need the number.)

**2. The macro leg IS a nearly-static beta bet, dressed as a conditional risk premium.**

VIX is one scalar time series. Trailing beta is highly persistent name-to-name. So cross-sectionally, `vix_riskpremium_scaled_beta` ≈ (a slowly-moving scalar) × (an almost-static beta rank). The Bull's rebuttal #2 concedes the differentiation *between names* comes entirely from beta magnitude — i.e. **most of the cross-sectional signal every rebalance is just "overweight high-beta,"** the low-vol anomaly run in reverse. The VIX modulation only steepens it at the 3–5 spikes. Strip the spikes and you are left with a static beta tilt. That is not a new macro axis; it is a beta bet with a volatility knob.

**3. The macro leg is the validation artifact, and it is explicitly selection-fit.**

The Bull's own justification indicts it: *"iter 16 already committed the campaign to 'elevated VIX = bullish forward' and it held in all three sectors... this leg pins it positive and cannot invert."* That is the Campaign-1 failure verbatim — a sign chosen *because it worked on prior data*, then hard-coded. Campaign 1 scored +0.0521 on validation and **−0.0118 on holdout** doing exactly this.

"Elevated VIX → bullish 21-day forward" is mechanically "buy the vol spike," which worked across a decade of central-bank-backstopped mean reversion (2018, 2020, 2022 all V-shaped up). In a holdout regime where a spike is followed by *continuation* (2008-style, or any non-rescued drawdown), the sign flips and the leg becomes negatively predictive. Pinning the sign so it "cannot invert" is sold as safety — it is the opposite. It removes the model's ability to adapt and **hard-codes the validation-era regime into the holdout.** The rigidity is the tell, not the guardrail.

The profitability leg, by contrast, rests on a genuinely replicated, mechanism-first anomaly (Novy-Marx RMW). If one leg survives, it is that one. Which raises the obvious question for the Manager: dropping to the single profitability factor reintroduces the single-signal failure mode — but pairing it with a beta-straddle macro leg that half-cancels it is not a real bundle either.

**4. Point-in-time exposures — both real, neither confirmed.**

- The Bull flags operating income must be **filing-date stamped**. Add the sharper risk: operating-income fields in most feeds are frequently **restated in place**, so `data_available=True` does not guarantee the value on the row's date is the value that was *public* on the row's date. Confirm the vintage is as-first-reported, not as-currently-carried.
- The macro leg needs "elevated VIX" defined on a **strictly backward window.** If "elevated" is a z-score or threshold calibrated against a full-sample mean/percentile, the leg peeks at the future distribution of VIX. This is unstated in the proposal and must be pinned down — it is a silent lookahead vector.

**Bottom line for the Manager:** the profitability leg is defensible. The `vix_riskpremium_scaled_beta` leg is (a) a static beta bet masquerading as a conditional premium, (b) sign-fit to iter 16 — the exact selection pressure that sank Campaign 1 — and (c) it does not orthogonalize the bundle, it puts a *second, opposite* bet on the same beta axis so the two legs partly cancel and the score reduces to one regime-dependent coin flip. That is not diversification; it is a single-axis straddle with a validation-fit sign. Strongest objection: this bundle's headline virtue is fictional.


## Research manager decision

SELECTED: operating_profitability_rmw

REASONING:
The bear and the external reviewer independently landed the same decisive blow on `vix_riskpremium_scaled_beta`, and it is fatal on three counts:

1. **The interaction likely vanishes algebraically.** The evaluator ranks/normalizes cross-sectionally within (date, industry). Multiplying every name's *positive* beta magnitude by one *positive* VIX scalar is a monotonic transform that leaves the within-date ordering unchanged — so the "conditional risk premium" reduces to a plain trailing-beta rank. The VIX knob adds nothing to the cross-section on any normal day. The Bull conceded exactly this in rebuttal #2 ("differentiation between names comes entirely from beta magnitude"). It is the low-vol anomaly run in reverse, not a new macro axis.

2. **The orthogonality claim is false — it's a single-axis straddle.** The Bull's headline virtue was that profitability sits low-beta and VIX×beta sits high-beta, so "they can't be collinear." Opposite ends of the *same* axis is anti-correlation, not orthogonality. The two legs would half-cancel and the bundle's score would collapse to the sign of one beta bet in the sealed window — the concentrated, regime-determined exposure the bundle design exists to avoid. Padding to two factors here makes the bundle *worse*, not more robust.

3. **The sign is selection-fit — the Campaign-1 failure verbatim.** "Elevated VIX = bullish forward" was retained *because* it worked in iter 16's three sectors, then hard-coded so it "cannot invert." That is not a guardrail; it hard-codes the validation-era (backstopped, V-shaped) regime into the holdout and removes any ability to adapt to a continuation regime. Campaign 1 did exactly this: +0.0521 val → −0.0118 holdout.

**Why one factor, not two.** The rule against lone factors is real, and I am not waving it away: a single factor makes this iteration another best-of-N draw. But the only second axis on the table is dead on arrival — it is redundant (a beta rank), anti-correlated on that same axis, and a validation artifact. A weaker-but-orthogonal factor would break the best-of-N pattern; a factor that is *both* an artifact *and* loads on the same axis as the survivor does not — it reintroduces concentration while adding noise. There is no genuinely independent, pre-specified second factor proposed this iteration, so none survives. I will not manufacture diversification by including a leg the debate proved fictional.

**Binding conditions on the surviving leg** (both raised by Bull and Bear; non-negotiable for implementation): operating income must be stamped **as-first-reported by filing date, point-in-time** — not fiscal-period-end, and not a restated-in-place vintage. If the feed only carries as-currently-carried values, this factor is not buildable honestly and the iteration should report that rather than ship a leaky factor.

Directive to the Macro Analyst for next iteration: bring a factor whose cross-sectional signal survives the evaluator's within-date normalization and whose forward-payoff conditioning (not just scale) is shown in preregistered diagnostics — a sign-fixed scalar × static rank will keep failing this bar.


## Selected factors
operating_profitability_rmw
