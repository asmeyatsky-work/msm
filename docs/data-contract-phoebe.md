# Data contract — Phoebe (GA4 behavioural features)

**Status:** Draft — sign-off blocks PRD V2 §2.1 item 8 going live.
**Companion to:** `docs/data-contract-credit-cards.md` (click + sales-ledger).
**Scope:** GA4 BigQuery export feeding `rpc_estimator.phoebe_features` and,
through the rpc_training_rows view, the Predictive RPC Estimator model
for Credit Cards.

---

## 1. What we ingest

A nightly read of the client's GA4 BigQuery export for the Credit Cards
property. The platform service account needs **BigQuery Data Viewer** on
the export dataset (typical name: `analytics_<property-id>`) and the
property-level events tables (`events_YYYYMMDD`, `events_intraday_YYYYMMDD`).

We do **not** ingest:
- Raw `user_id` (Google-assigned, identifies a person across devices).
- Raw `ga_session_id` (Google-assigned, identifies a session).
- Page-view URLs containing PII querystring params (we strip
  `?email=`, `?phone=`, `?reference=` patterns at the staging view).
- Any custom event params whose key matches `email|phone|name|dob|address`.

We **do** ingest:
- `user_pseudo_id` — opaque hashed cookie identifier, GA4-default.
- `event_timestamp`, `event_name`, `event_params` (filtered as above).
- `session_engagement_time_msec`.

---

## 2. Output schema (consumed by the model)

`rpc_estimator.phoebe_features`:

```
user_pseudo_id              STRING REQUIRED
window_end_ts               TIMESTAMP REQUIRED (table partition)
phoebe_calculator_used      BOOL REQUIRED
phoebe_guides_read          INT64 REQUIRED ≥0
phoebe_cards_compared       INT64 REQUIRED ≥0
phoebe_session_engagement_s FLOAT64 REQUIRED ≥0
```

Refresh cadence: **nightly**, computed over the last 30 days of GA4
events. Sub-hourly is the documented follow-up (ADR 0007 placeholder).

---

## 3. Event taxonomy — what counts as what

These are the **best-current-guess** mappings from the strategy doc to
GA4 event patterns. Validated against real MSM events in Week 2 of the
delivery plan; mismatches are the OQ-12 conversation.

| Phoebe feature | GA4 event match | Notes |
|---|---|---|
| `phoebe_calculator_used` | Any event whose `event_name` contains the substring `calculator` (e.g. `calculator_open`, `cashback_calculator_result`) | Bool — at least one in the 30-day window. |
| `phoebe_guides_read` | `event_name = "page_view"` AND `event_params.page_location` matches `/credit-cards/.*/guide` | Counted across the window. |
| `phoebe_cards_compared` | `event_name = "select_item"` AND `event_params.item_category = "credit_card"` | Counts **distinct** `event_params.item_id`. |
| `phoebe_session_engagement_s` | Sum of `event_params.engagement_time_msec` divided by 1000 | Across all events in the window. |

If MSM's GA4 implementation uses different names, the
`dataform/definitions/staging/phoebe_features.sqlx` view is the only
place that needs to change.

---

## 4. Refresh and consistency

- **Dataform run**: nightly at 03:00 UTC. The view is `type: "table"`
  so it materialises fresh each run.
- **Feature store sync**: a downstream job (per ADR 0007) pushes the
  table into the Vertex Feature Store keyed on `user_pseudo_id`,
  refreshed nightly.
- **Serving-time lookup**: `scoring-api` reads the four Phoebe values
  via the existing feature-store adapter at request time, using the
  click stream's `user_pseudo_id` as the join key. When the join
  misses (no GA4 record for this cookie, or no `user_pseudo_id` on
  the click), defaults (`false`, `0`, `0`, `0.0`) are used. The model
  is trained on rows that include those default values, so missing
  Phoebe is a legitimate signal rather than an error.

---

## 5. Click → cookie join (OQ-13, open)

The click stream needs to carry `user_pseudo_id` so the model can join
to Phoebe at training and serving time. Three options for how this
gets there:

1. **CM360 + GA4 join client-side.** The client emits `user_pseudo_id`
   on the click payload from a server-side merge. Preferred.
2. **First-party cookie pass-through.** The bidder reads MSM's
   first-party cookie at impression time and passes it as
   `user_pseudo_id`.
3. **No join.** Phoebe falls through to defaults for every click. The
   model still trains, but the Phoebe lift is zero. (This is the
   degenerate case — fine for staging, useless for the strategy.)

OQ-13 is the conversation with client engineering about which of the
three to ship.

---

## 6. PII boundary (extends ADR 0004)

Two invariants beyond the original ADR 0004:

1. **Hashed identifiers only.** `user_pseudo_id` is the GA4 default
   pseudo-identifier (cookie-scoped, not reversible to a person). Raw
   `user_id` is not ingested.
2. **No PII in event params.** The staging view drops any
   `event_params` key matching `email|phone|name|dob|address` before
   the row reaches `phoebe_features`. The strip list is the
   conservative default and lives in `phoebe_features.sqlx §events`.

A new ADR 0005 documents the boundary and the strip rules. Sign-off
by client compliance on §6 of this document is a release gate before
the `phoebe_features` view is enabled in the client env.

---

## 7. Retention

- `phoebe_features` rows are kept 90 days at table grain. The view
  rebuilds nightly so retention is per-snapshot.
- The upstream GA4 export retention is governed by the client's GA4
  configuration; we do not copy raw GA4 events into our environment.

Right-to-erasure: a deletion request on a `user_pseudo_id` is
satisfied by:
1. Deleting the corresponding row from `phoebe_features` (single-row
   delete in BigQuery).
2. Confirming the upstream GA4 row is purged by the client.
3. The next nightly rebuild reflects the deletion automatically.

SLA per `docs/data-contract-credit-cards.md §6` (24 hours).

---

## 8. Sign-off

This contract is binding once:
- Client analytics confirm the GA4 property ID and grant the platform
  SA the read role.
- Client compliance signs §6 (PII boundary).
- Client engineering responds to OQ-13 with one of the three
  click→cookie options.

Until all three land, the `phoebe_features` view materialises against
a non-existent dataset and the training join falls through to defaults
— no PII reaches the platform, no model is trained on Phoebe signal,
and the dashboard form sliders show how the model *will* respond when
the data is wired.

| Sign-off | Owner | Date |
|---|---|---|
| GA4 property + access granted | Client analytics | |
| PII boundary §6 | Client compliance | |
| Click→cookie option (OQ-13) | Client engineering | |
