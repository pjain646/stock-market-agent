# Multi-agent research pipeline — iteration 26

## Analyst team

### Fundamental analyst
(no output)

### Macro analyst
(no output)

### Sentiment analyst
(no output)

## Proposed factors

- **asset_turnover_efficiency** [fundamental] (data_available=True)
  Asset turnover (trailing Revenues / total Assets) is the *efficiency* leg of the DuPont ROA identity (ROA = margin × turnover), so it is orthogonal by construction to the two fundamental legs already in the peak bundle: it measures how productively a firm converts its asset base into sales, not its profit level (profmom) and not its leverage (equity/assets solvency). The mechanism is the operating-productivity anomaly — durable asset-utilization efficiency is a slow-moving quality trait the price-fixated market underweights, so high within-industry-turnover firms out-drift as that productivity is recognized gradually. It fills the one DuPont dimension the campaign has never isolated.

- **credit_spread_stress_scaled** [macro] (data_available=True)
  Credit markets price default risk earlier and more sign-stably than equity: when the high-yield-minus-investment-grade OAS (BAMLH0A0HYM2 − BAMLC0A0CM) is wide and widening, the market is demanding more to bear default/quality-migration risk, and lower-quality, more-cyclical equity cash flows get repriced down first and hardest. This is a distinct macro channel from the winning rate/duration leg — credit stress hits cyclicals and financials, rate duration hits long-duration growth — so it should be sign-stable and orthogonal, not another permutation of the DGS10/curve/VIX composite that has plateaued.


## Bull/bear debate (2 turns)


Bull Researcher: ## BULL CASE — open

Both legs clear the bar that killed Campaign 1 and the plateau: they add *new axes*, not permutations. Here is the concrete case, and where I think the bear will aim.

**1. Asset turnover is genuinely orthogonal — not "another quality factor."**

The DuPont identity is an accounting decomposition, so orthogonality here is structural, not empirical hope: ROA ≡ margin × turnover. The peak bundle already owns the *margin/profit level* dimension (profmom) and the *leverage* dimension (equity/assets solvency). Turnover is the third leg, and it is mechanically the residual — a retailer and a software firm can have identical ROA with inverse margin/turnover splits. That means turnover's cross-sectional dispersion is concentrated in exactly the firms where the existing legs are uninformative. Bear will say "quality factors collinear at the P&L level" — but collinearity of *inputs* isn't the test; the test is P&L covariance in the deciding regime, and margin and turnover diverge most precisely in the industries (asset-heavy cyclicals vs. asset-light) that dominate this 11-sector universe.

Mechanism is real and named: the operating-productivity anomaly. Durable asset-utilization efficiency is slow-moving and under-salient to a price-fixated market, so high-within-industry-turnover names out-drift as productivity is recognized. Within-industry ranking is essential — raw turnover is a sector proxy (utilities ~0.3, retail ~2.5). Built industry-relative, it is a clean quality trait, not a sector bet.

**2. Credit spread stress is a distinct macro channel, sign-stable by construction.**

The plateaued macro leg is the DGS10/curve/VIX rate-duration composite. HY−IG OAS is a *different transmission path*: rate duration reprices long-duration growth cash flows; credit stress reprices *default and quality-migration risk* in cyclicals and financials. Different firms, different sign driver. Bear will say "credit and VIX both spike in risk-off, so it's redundant." Partly true in tail weeks — but OAS leads equity and is sign-stable *between* tails, where VIX is mean-reverting noise. The correlation that matters is not "do they co-move in a crash" but "does credit carry incremental sign information in the 90% of months that decide a walk-forward score." It does: credit desks price migration risk that equity vol doesn't see until later.

**3. On the tuning lesson.** 27% of the last bundle's score was hand-set per-sector weights. Neither factor here needs per-sector parameters — turnover is industry-*ranked* (a transform, not a tuned weight) and credit stress is a single market-wide series. This bundle is structurally cheaper to overfit than the one that taught us that lesson. That is a point in its favor, not a coincidence.

Bear — the strongest attack is on credit/VIX redundancy in the holdout regime. Bring the specific co-movement claim and I'll engage it directly.

REPORT: Test both as proposed. Two new orthogonal axes (DuPont turnover residual; credit-default channel), each with a named mechanism, both point-in-time-safe, and neither reintroduces the per-sector tuning failure. This is exactly the kind of new-axis bundle the plateau calls for.
Bear Researcher: ## BEAR CASE

I'll take both, hardest first.

**1. credit_spread_stress_scaled is a single macro time series — it has no cross-section, and it shares its sign-driver with the incumbent leg.**

This is the factor most likely to be a validation artifact, and the reason is structural, not a correlation I'm guessing at. HY−IG OAS is one market-wide number: on any given date it is *identical for all 166 names*. So it carries zero cross-sectional information by itself — it can only act as a regime/timing overlay (or via an interaction with beta/cyclicality that nobody has specified in the proposal). The winning rate/duration leg (DGS10/curve/VIX) is *also* a market-wide regime overlay. The Bull's defense is "different transmission path" — true at the mechanism level, but the Judge doesn't score mechanisms, it scores P&L, and at the P&L level both legs collapse to the same latent variable: risk-on vs. risk-off. Credit widens, VIX spikes, curve moves — these are not independent draws, they are one macro state.

The killer is effective sample size. A single macro series over a walk-forward has maybe a dozen *independent* 21-day regime episodes (2011, 2015–16 energy, late-2018, 2020, 2022). "Incremental sign info in the 90% of non-tail months" (Bull's point 2) cuts the *wrong* way for us: between tails, OAS is slow-moving and near-constant, so those months contribute almost no independent variation — the fit is dominated by a handful of widening episodes. That is Campaign 1's exact failure mode (a noisy signal fitting a few validation-window events, then −0.0118 on holdout), promoted from the single-stock level to the macro-regime level. A bundle doesn't immunize a leg that is itself a noisy max over a few regime transitions.

**2. "scaled" is an undeclared tuning knob.** The name is `credit_spread_stress_*scaled*` — scaled how? If it's z-scored/normalized over a rolling window, the lookback length is a hyperparameter, and if it's normalized over full-sample stats it leaks. The Bull claims this bundle is "structurally cheaper to overfit" because no per-sector weights — but a normalization window is precisely the kind of hidden knob that the 27%-tuning lesson warns about. Specify the scaling and confirm it's PIT and untuned, or this claim is empty.

**3. Selection pressure is explicit in the credit proposal.** The proposal *names* the winning leg and picks credit because risk-off is what drove past performance. Choosing a factor because it correlates with the regime that already scored well is fitting to what worked — the same pressure that inflated Campaign 1.

**4. asset_turnover_efficiency: the DuPont-orthogonality argument is a sleight of hand, and there's a corporate-action artifact.**

The Bull says the peak bundle "owns the margin/profit-level dimension via profmom." It does not. **profmom is profit *momentum*, not margin level** — it's a change/trend signal, not the DuPont margin leg. So the clean "ROA ≡ margin × turnover, we own two legs, this is the third" story is missing its middle term. Turnover is not the residual of two owned legs; it's a new leg next to a *momentum* leg and a *leverage* leg. Orthogonality may still hold empirically, but the structural guarantee the Bull leans on doesn't exist. It's unmeasured — don't sell it as mechanical.

The subtler failure: **turnover = trailing Revenues / total Assets is distorted by M&A.** A large acquisition inflates the asset denominator on the filing date and mechanically *drops* turnover overnight — that's a corporate-action artifact, not a change in operating productivity. In a large-cap universe acquisitions are frequent, and the signal will systematically short recent acquirers. That is not "the market underweighting durable efficiency"; it's a balance-sheet event. Unless the construction handles goodwill/acquired-asset jumps, the factor is partly measuring deal activity.

**5. Thin-bucket noise.** Turnover *must* be industry-ranked (Bull concedes raw turnover is a sector proxy). With 166 names across 11 sectors, industry buckets are ~10–15 names. Ranking a slow-moving fundamental within 12-name buckets is a noisy transform — small denominators, and the "productivity anomaly" drift has to overcome that noise to show up in a 21-day forward window. It may; it's unmeasured.

**REPORT:** Neither factor is a clean point-in-time leak, so both are testable — but with conditions. **credit_spread_stress_scaled is the weak leg**: it's a zero-cross-section macro overlay collinear with the incumbent risk-off regime, with ~a dozen effective observations, an undeclared "scaled" hyperparameter, and explicit selection pressure toward the regime that already worked — the highest artifact risk in the bundle. Require the scaling spec (window, PIT-safe) and, if it enters via an interaction, name the interaction before testing. **asset_turnover_efficiency is the sounder leg** but the DuPont-residual framing oversells orthogonality (profmom is momentum, not margin), and construction must neutralize M&A-driven asset jumps or it will short recent acquirers. Test turnover; treat credit as on-probation and be unsurprised if it's the leg that doesn't survive the holdout.


## Research manager decision

SELECTED: asset_turnover_efficiency

REASONING:

**Credit is dropped, and the reason is structural, not a strength comparison.** The bear and the external reviewer converged on the decisive point: `credit_spread_stress_scaled` is a single market-wide series, *identical for all 166 names on any given date*. As proposed it has zero cross-section, so it cannot rank stocks — it can only act as a risk-on/risk-off timing overlay. That is the same latent variable the incumbent DGS10/curve/VIX leg already trades. The Bull's "different transmission path" is true at the mechanism level and irrelevant at the P&L level, where both collapse to one macro state with ~a dozen independent regime episodes. That is Campaign 1's failure mode (a noisy fit to a few validation-window events) promoted to the macro level, and a bundle does not immunize a leg that is itself a noisy max over a handful of regime transitions. Compounding it: the proposal *names the winning leg* and selects credit because it correlates with the regime that already scored — explicit selection pressure toward what worked. And "scaled" is an undeclared normalization knob (window length or full-sample leak) that reintroduces the tuning risk the 27%-ablation lesson warns about. To even enter the cross-section it needs an unspecified beta/cyclicality interaction — which would add a *new* selection opportunity, not remove the problem. This leg is not testable as written.

**Turnover survives, but the Bull oversold it and the bear's corrections are binding.** The clean "ROA ≡ margin × turnover, we own two legs" story is wrong: the bear is right that **profmom is profit momentum, not the margin level**, so the structural orthogonality guarantee doesn't exist — orthogonality here is an empirical hope, not an identity. It's still a plausibly distinct axis (asset productivity vs. a momentum leg and a leverage leg) with a named mechanism. But it is testable **only with these preregistered conditions**: (1) PIT filing-date lags; (2) within-industry neutralization; (3) explicit M&A/goodwill treatment so the factor doesn't mechanically short recent acquirers on denominator jumps; (4) a control or caveat for asset-age/intangible-intensity bias (external reviewer's point — old depreciated plant and uncapitalized intangibles inflate turnover without real efficiency). Without these it partly measures deal activity and accounting structure, not productivity.

**Why one factor, not two.** The charter's presumption against single-factor selection exists to avoid best-of-N selection pressure, and I take it seriously. But that presumption assumes the second axis is merely *weaker* — a weaker-but-orthogonal factor would still break the pattern and I would keep it. That is not the situation here. Credit as proposed is **structurally incapable of the task**: a series with no cross-section cannot predict relative stock direction, full stop. Adding it would not create a genuine two-axis bundle — it would spend an evaluator trial on a timing overlay collinear with the incumbent, obscuring attribution on the one leg that can actually be measured. Padding to two with a disqualified leg is worse than one clean, preregistered test. If we want a true second axis next iteration, it must carry real cross-sectional content (e.g., firm-level credit sensitivity or an accruals/investment leg), proposed ex ante — not a macro scalar chosen because it hugs the regime that already won.


## Selected factors
asset_turnover_efficiency
