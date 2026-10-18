# Email draft (Gmail — created as draft, never sent)

**Subject:** `Weekly Product Pulse + Customer Clarification — 2026-10-18`

**To:** *(left empty — draft only)*

**Body:**

```text
INTERNAL DRAFT — NOT SENT

================================================================
1. WEEKLY PRODUCT PULSE
================================================================

Period: 11 Aug – 16 Oct 2026 · Sample: 1,000 stratified reviews of 10,000 · Prepared: 18 Oct 2026

Baseline. 814 of 1,000 reviews (81%) carry no substantive complaint, tracking a 768/1,000 five-star skew. Counts below are complaint volume in this sample, not shares of the customer base.

Top issue themes: Technical Issues (73), Feature Requests (44), Poor Customer Support (28). High Fees (24) is this week's fee focus.

What users said

- Technical — "Most of the time, the stop-loss doesn't get placed, and because of this, I end up taking losses." (3★, 7 Oct, e6afdabd)
- Support — "requesting a simple spelling change of my surname 1 month ago and still pending" (1★, 20 Sep, ec74a5f0)
- Fees — "kharine pr 10 aur bechne pr 30" — ₹10 on buying, ₹30 on selling (1★, 18 Sep, 01d9c2da)

Key observation. Technical complaints concentrate on the order path: stop-loss not placing, hangs while ordering, login failure in market hours. These are revenue-path defects, not cosmetic.

Fee complaints are not about price level. Users are confused by asymmetry — the sell leg debits more than the buy leg, reading as a double charge. 19 of 25 fee-mentioning reviews are rated 3★ or below.

Actions

1. Alert on order-placement failure rate during market hours; stop-loss is highest severity.
2. Ship a pre-trade charge breakdown splitting buy and sell, naming DP charges as sell-side only.
3. Put an SLA on non-trade support requests (name, KYC); cheap to resolve, reliably produce 1★ reviews.

================================================================
2. CUSTOMER FEE EXPLANATION (reusable support snippet)
================================================================

Why a sell costs more than a buy:

  • Equity brokerage is ₹20 or 0.1% of the executed order value, whichever is lower, subject to a ₹5 minimum per executed order. This applies to both buy and sell orders.
  • DP (depository) charges apply only when shares leave your demat account — that is, on sell transactions only. They are charged per sell transaction, not per share, so selling 5 shares and 500 shares of the same stock carry the same DP charge.
  • Current DP charges are ₹3.5 per sell transaction to the depository (₹3.25 for women) plus ₹16.5 to Groww. The Groww component is ₹0 when the sell value is under ₹100.
  • This is the usual reason a sell leg costs more than a comparable buy leg: DP charges apply on the sell side only, while stamp duty applies on the buy side only. It is one charge per leg, not the same charge applied twice.
  • Statutory charges differ by side. On delivery trades, STT is 0.1% on both buy and sell; stamp duty is 0.015% on the buy side only; exchange transaction and SEBI turnover charges apply to both sides.
  • 18% GST applies to brokerage, DP charges, exchange transaction charges and SEBI turnover charges. It does not apply to STT or stamp duty. The exact amounts for any single trade are itemised in that trade's contract note.

Official sources:
  https://groww.in/pricing
  https://groww.in/help/stocks/searchable/when-are-dp-charges-levied

Last checked: 2026-10-18
```
