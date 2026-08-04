# Multi-agent research pipeline — iteration 33

## Analyst team

### Fundamental analyst
(no output)

### Valuation analyst
Both required inputs are proven-buildable point-in-time here: trailing annual `Revenues` from EDGAR as-first-reported (already pulled and used in iter 32's operating-margin leg) and the market-cap machinery (split-adjusted `CommonStockSharesOutstanding` × `adj_close`) proven in iter 21's earnings_yield. So sales_yield = trailing_annual_Revenues / market_cap, sector-demeaned, no new data risk.

### Macro analyst
The journal is unusually decisive on my axis, so I am proposing the proven sign-stable rate-pressure timer rather than a novel broadening attempt — because every broadening attempt has been killed for the same structural reason, and re-proposing them would be relitigating settled debates.

### Sentiment analyst
(no output)

## Proposed factors

- **accrual_reliability_earnings_quality** [fundamental] (data_available=True)
  Sloan's (1996) accrual anomaly: the accrual component of earnings is far less persistent than the cash component, but the market fixates on headline net income and overweights accruals, so high-accrual firms systematically disappoint and underperform over the next quarter while cash-backed earners out-drift. I proxy the accrual component as NetIncome minus the year-over-year change in cash, scaled by average total assets — LOW accruals (earnings backed by real cash, not paper working-capital build) is the good direction. This is an earnings-QUALITY axis, mechanistically distinct from the peak bundle's capital-structure LEVEL (equity/assets solvency) and profitability CHANGE (ROA momentum) legs.

- **sales_yield_within_sector** [valuation] (data_available=True)
  Sales-to-price (trailing annual Revenues / market cap) is the least accounting-manipulable value ratio — revenue sits above every margin, accrual, tax, and buyback choice that distorts earnings and FCF. High sales-yield names are firms the market has marked down on *temporarily* depressed margins; when margins mean-revert the price re-rates, which is why P/S has historically been the most robust out-of-sample value ratio (O'Shaughnessy). Ranked sector-demeaned so structurally low-margin sectors (Staples, Utilities) aren't uniformly tagged cheap.

- **rate_pressure_duration_timer** [macro] (data_available=True)
  High and rising Treasury yields raise discount rates and are a pooled-negative headwind for forward returns across every sector in this large-cap universe — the sign never flips, only the magnitude scales with each name's cash-flow duration. A sign-stable bullish rate-conditions score (low/falling 10y level + change, steeper 10y-2y curve) scaled by a continuous, point-in-time per-name rate-sensitivity magnitude (|β| of trailing return-on-Δ10y, sign fixed) times WHEN the discount-rate tape is favorable and differentiates WHICH names lever that regime. This is the exact macro TIMING leg that carries the campaign's reproduced +0.0751 frame (iters 25/29/30/31) and whose removal collapsed iter 32 to −0.0108.


## Bull/bear debate (2 turns)


Bull Researcher: # BULL — the case for testing this bundle as proposed

## The two ranking legs are genuinely orthogonal, and the choice of *sales* yield is what makes them so

The strongest structural point in this proposal is one the Valuation Analyst half-buried: **sales_yield was chosen precisely because revenue sits above the line where accruals live.** This is not two value-ish factors stapled together.

- **accrual_reliability** measures *the composition of the earnings number* — cash-backed vs. paper working-capital build. It lives entirely on the accrual/net-income line.
- **sales_yield** deliberately prices the firm on the one figure that is *upstream of every margin, accrual, tax, and buyback choice.* Revenues/market_cap cannot be contaminated by the exact accrual distortion the fundamental leg is trading against.

So the usual bear objection to a "quality + value" pairing — that a cheap-on-earnings screen and a quality-of-earnings screen both key off the income statement and end up collinear — **is structurally defused by construction.** Earnings-yield would have overlapped accruals (both touch net income); the analyst picked the value ratio that mechanically doesn't. That is a real, defensible orthogonality argument, not a hope.

## Each leg has a named mechanism, not a pattern

- **Accruals (Sloan 1996):** market fixates on headline net income, overweights the low-persistence accrual component, high-accrual names disappoint over the forward quarter. 21-day forward horizon sits right in the drift window. Low-accrual = good direction. Documented, survived decades OOS.
- **Sales yield (O'Shaughnessy):** high P/S = market has marked the name down on *temporarily* depressed margins; re-rates on mean reversion. Sector-demeaned so Staples/Utilities aren't blanket-tagged cheap — this directly kills the "low-margin sectors dominate the long book" failure.
- **Rate timer:** discount-rate headwind, sign-stable, magnitude scaled by per-name cash-flow duration.

## On the macro leg — pre-empting the obvious bear shot

The charter is explicit that a *pure* macro factor is one number per date and rank-contributes zero. **This leg is not that.** It is a sign-fixed regime score *times a continuous per-name |β| rate-sensitivity magnitude.* On any given date it takes different values across the 166 names because the β differs — it differentiates WHICH names lever the regime, it doesn't just time WHEN. And critically, we are **not** dropping to fundamental+macro: we retain two real cross-sectional legs (accruals, sales_yield) AND the timer. This is the three-axis bundle the design wants, not the degenerate case the charter warns against.

It is also the leg carrying the reproduced **+0.0751** frame across iters 25/29/30/31, and whose removal *collapsed iter 32 to −0.0108.* That is the single most decisive ablation evidence in the campaign. Keeping it is the low-variance choice.

## Why this bundle is worth the iteration specifically

The plateau warning says another permutation of the *same three axes* won't break +0.057–0.065. **This bundle swaps in a genuinely new fundamental axis.** The peak bundle traded capital-structure LEVEL (equity/assets) and profitability CHANGE (ROA momentum). accrual_reliability is neither — it is earnings-*quality*, an axis the peak bundle never carried. Combined with sales_yield replacing an earnings-based value leg, **two of the three cross-sectional inputs are new mechanisms**, sitting on the one proven macro timer. That is exactly the "new axis beats refinement" move the campaign asked for, while holding the highest-confidence leg fixed to control variance.

## Data risk is near zero

Both new inputs reuse proven point-in-time machinery: trailing annual `Revenues` (iter 32's operating-margin leg) and the market-cap stack (iter 21 earnings_yield). No new EDGAR fields, no new PIT surface to leak.

**Bear:** your job is to find where these three co-move in the regime that decides the holdout. My claim is the sales/accrual pairing is the most orthogonality-defensible quality+value combo we've put up, because the value leg is chosen to sit above the accrual line. Show me the regime where a low-accrual screen and a high-sales-yield screen load the same names — I don't think you can do it on the income statement, so if the collinearity exists it has to come from somewhere else. Name it.
Bear Researcher: # BEAR — where this bundle fails out-of-sample

The Bull set the trap well: "show me where a low-accrual screen and a high-sales-yield screen load the same names — you can't do it on the income statement." Correct. I'm not going to. The collinearity that kills this bundle is **not** on the income statement, and it isn't between the two legs the Bull defended. It's between the value leg and the macro leg — the pairing nobody stress-tested.

## 1. sales_yield and the rate_timer are the same bet in the regime that decides the holdout

Trace the names each leg actually loads:

- **sales_yield** long book = high revenue/market-cap = names the market has *marked down on temporarily depressed margins*. The Valuation Analyst says so explicitly. Beaten-down, margin-compressed names are, empirically and mechanically, **cyclicals and short-duration value** — the stuff that gets marked down when the market prices a slowdown.
- **rate_timer** up-weights names by `|β|` of return-on-Δ10y — i.e. **high rate-sensitivity**. The names with the largest rate betas in a large-cap universe are the same cyclical / value / short-duration cohort.

So on a favorable-rate date the timer *scales up exactly the book sales_yield is already long*. Two of your three legs point the same direction, and they do it **precisely in the rate-regime transition that decides a holdout** — because that's when both the value re-rating AND the rate beta pay off together, or fail together. This is the charter's own warning realized: the macro leg isn't adding a third axis of *stock selection*, it's levering the value leg's book. You have **two real cross-sectional axes, not three** — accruals, and (sales_yield×timer collapsed into one value-cyclical bet). Sector-demeaning sales_yield does not save you: within a sector, the cheapest-on-sales name is still the most beaten-down, highest-rate-beta name in that sector. The demean removes the sector tilt, not the cyclicality that creates the overlap. **Unmeasured** — but it's a mechanism, and it's the one the Bull said didn't exist.

## 2. The accrual factor as-built is NOT Sloan, and the academic pedigree defense collapses with it

The proxy is stated as **"NetIncome minus the year-over-year change in cash, scaled by average total assets."** That is not the Sloan accrual. Sloan (1996) accruals = Δnon-cash working capital − depreciation. `NetIncome − ΔCash` is a crude *free-cash-flow* proxy, and ΔCash on the balance sheet is dominated by **financing and investing flows** — buybacks, debt issuance/paydown, capex, dividends, M&A. A firm that levers up and buys back stock shows a huge ΔCash that has *nothing to do with earnings quality*.

Two consequences:
- The Bull's entire defense — "Sloan, documented, survived decades OOS" — applies to a factor **this bundle isn't building**. You don't get to inherit Sloan's OOS pedigree for a FCF-minus-financing proxy.
- It **leaks straight into the capital-structure axis**. Financing-driven ΔCash *is* a capital-structure signal. So the claim that accrual_reliability is "mechanistically distinct from capital-structure LEVEL" is undermined by the proxy's own construction. Your genuinely-new axis is contaminated by the axis it claims to be orthogonal to.

## 3. The rate_timer is the most likely validation artifact — and keeping it is textbook selection pressure

The Bull's strongest evidence — "+0.0751 reproduced across iters 25/29/30/31, removal collapsed iter 32 to −0.0108" — is **equally consistent with the timer being a single-regime artifact**. Those iters share the same validation window and therefore the same realized rate path. A sign-fixed rate timer has effectively *one* degree of freedom; if the validation era contains one dominant rate episode, the timer will look magnificent in every iteration that reuses that window and collapse the instant it's removed — not because it captures a mechanism, but because the whole validation era *is* that one regime. Purged walk-forward doesn't rescue you here: purging removes horizon leakage, it does not manufacture independent rate cycles. There are maybe 2–3 real rate regimes in this sample; that is not an OOS base.

And "hold the highest-scoring leg fixed because it scored" **is** the keep-the-best-of-N move that failed Campaign 1 at +0.0521→−0.0118. The Bull reframes it as "low-variance." It's low-variance *on the validation set by construction* — that's what selection pressure looks like from the inside.

## What I'd concede

The accrual/sales-yield *income-statement* orthogonality argument is real — revenue does sit above the accrual line. The Bull won that specific point. It just isn't the point that matters, because the fatal overlap is sales_yield↔timer, and the accrual leg's problem is mis-specification, not redundancy with sales_yield.

## Bottom line for the Manager

- **Fix the accrual proxy** to real operating accruals (Δnon-cash WC − dep) or drop the Sloan pedigree claim — as written it's a FCF/financing hybrid, not an earnings-quality axis.
- **The three-axis claim is really two axes** once the rate regime hits: sales_yield and the timer co-load beaten-down high-rate-beta cyclicals. If the holdout turns on a rate move, expect their P&L to be one bet, and expect the bundle to inherit whatever the timer's single-regime luck was.
- The timer is the leg most likely to not survive a genuinely out-of-regime holdout, and it's being retained for exactly the reason Campaign 1 warns against.


## Research manager decision

SELECTED: accrual_reliability_earnings_quality (respecified to true operating accruals), sales_yield_within_sector

REASONING:

The bear and the external reviewer independently landed the same decisive blow on the macro leg, and it holds. **Drop rate_pressure_duration_timer.** Two separate defects, either sufficient:

1. **|β| destroys sign information.** Taking absolute rate sensitivity and imposing one universal sign pools banks, insurers, defensives, and long-duration growth into the same exposure bucket — names that mechanically move in *opposite* directions on a yield change. That converts estimation noise into confidently mis-signed positions. This is a construction defect, not a tuning choice.
2. **The +0.0751 replication is not independent confirmation.** Iters 25/29/30/31 reuse the same validation-era rate path; a sign-fixed timer with ~one degree of freedom will look identical across every iteration that reuses that window and collapse the instant it's removed — which is exactly what iter 32's −0.0108 shows, and is equally consistent with single-regime luck as with a real mechanism. Retaining it *because it repeatedly scored* is the precise keep-the-best move that failed Campaign 1 (+0.0521→−0.0118). The charter also warns a macro leg times WHEN, not WHICH — and the bear showed its per-name scaling co-loads the same beaten-down high-rate-beta cyclicals as sales_yield, so it wasn't buying a third selection axis anyway.

What the bear got right beyond the timer: **the accrual proxy as written is not Sloan.** `NetIncome − ΔCash` is a FCF/financing hybrid — balance-sheet ΔCash is dominated by buybacks, debt, capex, M&A — so it leaks straight into the capital-structure axis it claims orthogonality from, and it cannot inherit Sloan's OOS pedigree. This is a **respecification, not a kill**: the underlying earnings-quality axis is real and genuinely new (the peak bundle never carried it). **Build it as true operating accruals (Δnon-cash working capital − depreciation, scaled by average total assets), low-accrual = good.** If that is not cleanly point-in-time-buildable from available EDGAR fields, report back rather than shipping the FCF hybrid.

Why these two and not one: the bear *conceded* the income-statement orthogonality — revenue sits above the accrual line, so a cash-quality-of-earnings screen and a sales-to-price screen do not load the same names through the mechanism that drives either. Both rank stocks cross-sectionally. That gives two genuinely orthogonal cross-sectional axes — the shape the design wants — not a lone factor (Gate-1 failure mode) and not the degenerate fundamental+macro pair. With the timer gone, the sales_yield↔timer collinearity the bear identified disappears by construction.

Binding for implementation: (1) respecify accrual to real operating accruals or report it can't be built PIT-safe; (2) both legs sector-demeaned; (3) no per-sector weights — equal-weight the two legs, given ~27% of prior peak score was tuning-attributable.


## Selected factors
accrual_reliability_earnings_quality (respecified to true operating accruals), sales_yield_within_sector
