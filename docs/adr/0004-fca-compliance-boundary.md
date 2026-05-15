# ADR 0004 — FCA / Consumer Duty compliance boundary

**Status:** Accepted — 2026-05-15
**Context tag:** Credit Cards MVP

## Context

The Credit Cards MVP scores ad clicks for predicted revenue, used by
the bidding stack to set bids on Search Ads 360 (SA360) auctions.

The FCA's Consumer Duty (SYSC 22 / PRIN 12) and the FG21/1 fair-value
guidance govern decisioning models that influence the **product or
price offered to a customer**. Examples:

- Pricing of an APR offered to an applicant.
- Setting the credit limit on an approved card.
- Deciding whether to approve / decline an application.
- Tailoring the marketing creative shown to a customer in a way that
  routes them toward a different product.

What the Predictive RPC Estimator does:

- Scores a click context with the model's expected revenue.
- Returns that number to the bidding system.
- Logs the prediction for reconciliation.

What it does **not** do:

- It does not see, store, or act on individual customer identity.
- It does not influence the APR, fees, credit limit, or terms offered
  to any customer.
- It does not decide who is shown which card product. The creative
  inventory and routing logic remain in the client's marketing stack.
- It does not approve or decline anyone.

The model's output goes only to the bid auction. The auction outcome
(won or lost) is downstream of any customer-facing decision.

## Decision

The Predictive RPC Estimator sits **outside** the SYSC 22 / FG21/1
boundary that governs decisioning models. It is a **bid-optimisation
model**, not a decisioning model.

The boundary is enforced by two invariants:

1. **No customer-facing identifiers** are ingested. `click_id` and
   `correlation_id` are opaque to the bidder; they are not a hash of
   any customer attribute. Any future enrichment that crosses this
   boundary (e.g. ingesting customer credit-bureau data) is a separate
   ADR and requires compliance sign-off before merging.

2. **No model output is forwarded to anything that affects customer
   terms.** Predictions go to: (a) the bidding stack, (b) BigQuery for
   reconciliation, (c) the activation service for SA360 / SSGTM. None
   of these influence the product or price the customer is offered.

## Consequences

**Positive**
- The MVP can ship without going through a Consumer-Duty-grade model
  governance review, which would add weeks to delivery.
- The audit-trail requirement is satisfied by the existing reconciliation
  pipeline (every prediction is logged, every attribution recoverable).

**Negative**
- The invariants are load-bearing. Any future product change that
  routes the model's output to a customer-facing surface (e.g.
  "personalised credit-card recommendation engine") moves the model
  back inside the boundary and triggers a full re-assessment.

**Neutral**
- This is not legal advice; the client's compliance contact should
  countersign the boundary as part of the data-contract sign-off
  (`docs/data-contract-credit-cards.md`). Searce's role is to record
  the boundary, not to grant it.

## Implementation notes

- `services/scoring-api/crates/domain/` already rejects requests
  carrying identifiers it doesn't know how to handle (reject-by-default).
  No changes needed.
- The data contract calls out PII handling explicitly and the
  sign-off block names a compliance contact.
- A short PII inventory lives at the bottom of
  `docs/data-contract-credit-cards.md`.
- If the boundary ever needs to be revisited, a new ADR supersedes
  this one; the model is not redeployed to a customer-facing surface
  until the new ADR is `Accepted`.
