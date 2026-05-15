# Resume here — Predictive RPC Estimator, Credit Cards MVP

_Self-orientation doc for next-week-Allan. Everything is in this repo;
nothing depends on local state on this laptop._

**Repo:** https://github.com/asmeyatsky-work/msm
**Branch:** `main`
**Latest commit:** `1ce5c89` (PRD V2 landed 2026-05-15)

---

## 1. Where you left off

The V1 demo was given to the client on **2026-05-12**. The client
confirmed Credit Cards as the MVP target. V1 is operational on
staging; V2 (Credit Cards) build is **planned, foundationally
started, and ready to execute starting week of 2026-05-18**.

What's live right now:

| Surface | URL | Status |
|---|---|---|
| Executive dashboard (V1) | https://dashboard-staging-794974391956.europe-west2.run.app | live, min=1, interactive prediction working |
| Scoring API | https://scoring-api-staging-794974391956.europe-west2.run.app | live, min=1, `/v1/score`, `/v1/explain`, `/health` |
| Reconciliation API | https://reconciliation-staging-794974391956.europe-west2.run.app | live, min=1 |
| GCP project | `msm-rpc` (number 794974391956), region `europe-west2` | — |
| Vertex AI endpoint | `rpc-estimator-endpoint`, model `rpc-estimator@1` | min=1 on e2-standard-2 |
| BigQuery dataset | `msm-rpc:rpc_estimator_staging` | populated with synthetic data + seeded demo rows |

V1 cost baseline: ~£3-5/day (Vertex endpoint dominant, plus three
Cloud Run services at min=1 for demo warmth).

---

## 2. Read these, in this order

1. **`docs/PRD-v2-credit-cards.md`** — the source-of-truth build spec.
   545 lines, 16 sections. Read once end-to-end. The §13 delivery plan
   is your weekly checklist; §14 open questions is your "ask the
   client first" list.
2. **`docs/credit-cards-mvp-changes.md`** — engineering change plan.
   File-by-file inventory of what changes and what doesn't. Reference
   while building.
3. **`docs/data-contract-credit-cards.md`** — schemas + PII inventory.
   This is the artefact the client signs. Phrase any kickoff-call
   asks in its language.
4. **`docs/adr/0003-credit-cards-conversion-reward.md`** — sum-of-rewards
   label choice for MVP.
5. **`docs/adr/0004-fca-compliance-boundary.md`** — bid-optimisation
   vs decisioning boundary. Two enforceable invariants. Compliance
   sign-off gates the release.
6. **`README.md`** — current platform topology, every Cloud Run
   service, every BQ view, every Pub/Sub topic. Use as a reference,
   not a primary read.

Optional / context:
- `docs/SOW.md` — original SOW from V1.
- `docs/client-demo-deck.pptx` — V1 demo deck. Architecture diagram
  on slide 6 is the image render the client liked.
- `docs/client-response-credit-cards-mvp.md` — draft reply to the
  client's 2026-05-15 confirmation. Edit and send.

---

## 3. What's already shipped for V2 (commit `4233928`)

These are in `main`; no work needed.

- **ADR 0003** — sum-of-rewards conversion modelling.
- **ADR 0004** — FCA / Consumer Duty boundary.
- **`docs/data-contract-credit-cards.md`** — Credit Cards schemas and PII.
- **`predictions_vs_revenue` view** — promoted to a Terraform resource
  using `var.reconciliation_window_days` (default 30; Credit Cards
  env will set 90).
- **Coverage-audit Dataform view** at
  `dataform/definitions/monitoring/coverage_audit.sqlx`. Will run on
  first real-data sample.
- **Dashboard 7 / 30 / 90-day window selector** live.

---

## 4. First three things to do next week

In strict order:

### Step 1 — answer as many of the 10 open questions as you can

`docs/PRD-v2-credit-cards.md §14`. Of the ten, these three unblock
the most:

- **OQ-1** GCP project (client's own vs namespace in `msm-rpc`).
- **OQ-3** Credit Cards click volume per `product_type` per day.
- **OQ-4** Sales-ledger join key.

If you can't answer them yet, they're the agenda for the kickoff call.

### Step 2 — send the client response

`docs/client-response-credit-cards-mvp.md`. Edit tone, send. Asks for
the data sample + nominated contacts + sign-off + a 60-min call slot.

### Step 3 — start the feature schema migration

The biggest single piece of work that can start without client data,
because the schema is documented in `docs/data-contract-credit-cards.md
§3`.

Files to touch (in dependency order):

```
services/scoring-api/crates/domain/src/click_features.rs
services/scoring-api/crates/presentation/src/main.rs   # ScoreRequest struct
services/ml-pipeline/src/.../training_rows_schema.py   # if explicit
dataform/definitions/training/rpc_training_rows.sqlx
dashboard/src/presentation/App.tsx                     # DEFAULTS + form fields
dashboard/src/presentation/labels.ts                   # plain-English mapping
proto/                                                  # if cross-service contracts exist
```

Replace generic features (`cerberus_score`, `rpc_7d`, `rpc_30d`,
`is_payday_week`) with the Credit Cards set
(`product_type`, `card_product_id`, `affinity_score`, `prior_applicant`,
`income_band_bucket`, `rpc_14d`, `rpc_60d`). ~3-4 engineering days.

---

## 5. Useful commands

All from the repo root.

```bash
# Verify staging is live
curl -s https://scoring-api-staging-794974391956.europe-west2.run.app/health
curl -s https://dashboard-staging-794974391956.europe-west2.run.app/api/reconciliation\?start=0\&end=9999999999999 | jq length

# Deploy a fresh dashboard image (Cloud Build → Cloud Run; bypasses CD)
cd dashboard && TAG=demo-$(date +%Y%m%d-%H%M%S) && \
  gcloud builds submit --tag europe-west2-docker.pkg.dev/msm-rpc/rpc-estimator/dashboard:$TAG \
    --project=msm-rpc --region=europe-west2 . && \
  gcloud run deploy dashboard-staging \
    --image=europe-west2-docker.pkg.dev/msm-rpc/rpc-estimator/dashboard:$TAG \
    --project=msm-rpc --region=europe-west2 --quiet

# Trigger CD via tag (full pipeline)
git tag -a v0.2.0 -m "Credit Cards build kickoff" && git push origin v0.2.0

# Trigger CD via manual dispatch (no tag)
gh workflow run cd.yml --ref main -f env=staging
gh run watch $(gh run list --workflow=cd.yml --limit 1 --json databaseId -q '.[0].databaseId') --exit-status

# Local dashboard dev
cd dashboard && ./node_modules/.bin/vite --port 5173 --host 127.0.0.1
# Then http://127.0.0.1:5173 — proxies /api to reconciliation-staging,
# /score and /explain to scoring-api-staging

# Quick scoring API smoke
curl -X POST https://scoring-api-staging-794974391956.europe-west2.run.app/v1/score \
  -H 'content-type: application/json' \
  -d '{
    "click_id":"smoke-1","correlation_id":"c-1","device":"mobile","geo":"GB",
    "hour_of_day":14,"query_intent":"commercial","ad_creative_id":"demo",
    "cerberus_score":0.62,"rpc_7d":1.85,"rpc_14d":1.92,"rpc_30d":1.78,
    "is_payday_week":false,"auction_pressure":0.55,"landing_path":"/",
    "visits_prev_30d":3
  }'
```

---

## 6. Cost defence after demo / handover

Three things drop spend when the client engagement winds down:

```bash
# 1. Drop dashboard + reconciliation to min=0 (cuts ~£1.50/day)
gcloud run services update dashboard-staging      --min-instances=0 --project=msm-rpc --region=europe-west2
gcloud run services update reconciliation-staging --min-instances=0 --project=msm-rpc --region=europe-west2

# 2. Scale Vertex endpoint to zero (cuts ~£2/day — see docs/runbooks/endpoint-scale-down.md)
gcloud ai endpoints undeploy-model 4471390533746425856 \
  --deployed-model-id=5983535681287225344 \
  --region=europe-west2 --project=msm-rpc

# 3. Drop scoring-api to min=0 (cuts a few pence/day)
gcloud run services update scoring-api-staging --min-instances=0 --project=msm-rpc --region=europe-west2
```

---

## 7. The 8-week calendar at a glance

(Detail in `docs/PRD-v2-credit-cards.md §13`.)

```
W1 (18-22 May)  kickoff · contract circulated · GCP decision · schema migration starts
W2              data sample lands · coverage audit · env stood up · ingestion live
W3              v1 trained on 50% · canary 10% on client env · drift live
W4              v1 to 100% on client env · runbooks rehearsed
W5              monitoring tuned · per-segment drift · prep for v2
W6 (end-June)   80% coverage data delivered · v2 retrained
W7              v2 canary 10% → 50% with active-versions panel live
W8 (end-July)   v2 to 100% · v1 decommissioned · handover sign-off
```

Aggressive: 6 weeks. Conservative: 10 weeks. The biggest slips are
the data contract sign-off (legal/compliance review can stretch from
days to weeks) and systematic missingness in the 50% sample (+5-7
engineering days if it turns out concentrated rather than random).

---

## 8. People & accounts

- **GitHub repo:** `asmeyatsky-work/msm`; branch protection on `main`
  is **removed** (direct commits allowed; see feedback memory).
- **GCP project:** `msm-rpc` (`794974391956`); region `europe-west2`.
- **WIF provider:** `projects/794974391956/locations/global/workloadIdentityPools/github-staging/providers/github-oidc`.
- **Service accounts:** `scoring-api-staging@`, `activation-staging@`,
  `breaker-automation-staging@`, `ci-deployer-staging@`.

Memory files in `~/.claude/projects/-Users-allansmeyatsky-msm/memory/`
will reload state for future Claude sessions. If they're wiped by the
laptop reset, the README + this doc + the PRD are sufficient to
rebuild context — the memory files are convenience, not authority.

---

## 9. Done? Quick gut-check

When you've finished V2, all of these should be true:

- [ ] Client env (`client-cc` or equivalent) serves `/v1/score` and
      `/v1/explain` against `rpc-estimator@2` trained on real
      80%-coverage data.
- [ ] Dashboard at the client URL shows real Credit Cards
      reconciliation in a 90-day window.
- [ ] Coverage panel reflects the latest audit.
- [ ] Active-versions panel shows v2 at 100% and v1 decommissioned.
- [ ] Per-segment drift monitors firing into the client's notification
      channel.
- [ ] Runbooks rehearsed once each with the client on-call.
- [ ] Rollback dry-run completed.
- [ ] Client compliance contact signed `data-contract-credit-cards.md §8`.
- [ ] Client engineering lead + data owner signed off on handover.

Good luck.
