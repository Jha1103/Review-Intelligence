# Weekly Product Pulse — Groww (Android)

**Period:** 11 Aug – 16 Oct 2026 · **Sample:** 1,000 stratified reviews of 10,000 · **Prepared:** 18 Oct 2026

**Baseline.** 814 of 1,000 reviews (81%) carry no substantive complaint, tracking a 768/1,000 five-star skew. Counts below are complaint volume in this sample, not shares of the customer base.

**Top issue themes:** Technical Issues (73), Feature Requests (44), Poor Customer Support (28). High Fees (24) is this week's fee focus.

**What users said**

- **Technical** — "Most of the time, the stop-loss doesn't get placed, and because of this, I end up taking losses." (3★, 7 Oct, `e6afdabd`)
- **Support** — "requesting a simple spelling change of my surname 1 month ago and still pending" (1★, 20 Sep, `ec74a5f0`)
- **Fees** — "kharine pr 10 aur bechne pr 30" — ₹10 on buying, ₹30 on selling (1★, 18 Sep, `01d9c2da`)

**Key observation.** Technical complaints concentrate on the order path: stop-loss not placing, hangs while ordering, login failure in market hours. These are revenue-path defects, not cosmetic.

Fee complaints are not about price level. Users are confused by *asymmetry* — the sell leg debits more than the buy leg, reading as a double charge. 19 of 25 fee-mentioning reviews are rated 3★ or below.

**Actions**

1. Alert on order-placement failure rate during market hours; stop-loss is highest severity.
2. Ship a pre-trade charge breakdown splitting buy and sell, naming DP charges as sell-side only.
3. Put an SLA on non-trade support requests (name, KYC); cheap to resolve, reliably produce 1★ reviews.
