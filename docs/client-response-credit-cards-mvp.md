# Response — Credit Cards Predictive Bidding MVP

_Draft response to the client's note dated 2026-05-15. Edit freely; the
intent here is a balanced, executive-friendly reply that addresses the
50% coverage question head-on, lists what we'd need to proceed, and
confirms the call._

---

Thanks for the confirmation, and for picking Credit Cards — it's a
sensible choice for the reasons you laid out, and the trajectory on
sales coverage (50 → 80% by end of June) actually fits the way the
platform retrains and canary-deploys, which I'll cover below.

## On the 50% sales coverage

Short version: **50% coverage is workable for a Phase-1 MVP, but the
*shape* of the missingness matters more than the percentage.**

The model uses click features at the time of bidding — those are
unaffected by sales coverage. Sales data is needed only at training
time to provide the label (what each historic click actually earned).
So 50% coverage doesn't reduce our ability to score live clicks; it
only reduces the sample we train on and our ability to back-test
accuracy on the unseen half.

Two scenarios to distinguish:

| Pattern of the missing 50% | Impact on the model | What we'd do |
|---|---|---|
| **Random** — coverage gaps are roughly evenly spread across channels, partners, devices, dates. | Minor. The model trains on a smaller-but-representative sample. Calibration on the visible 50% should generalise to the unseen half. | Train and ship; monitor for drift; recover the gap automatically as coverage climbs to 80%. |
| **Systematic** — the missing 50% is concentrated (e.g. one partner network, offline channels, a specific time window, certain card products). | Material. The model will be biased toward the visible segments and may systematically over- or under-price clicks in the unseen segments. | Either segment the model by the missing dimension and serve a fallback for the unseen portion, or fix the ingestion gap before training. |

This is the first thing we'd want to characterise once we have a data
sample. Practically, we'd run a short coverage audit (a day's work)
that splits the 50% along the obvious dimensions — partner, channel,
device, card product, attribution window — and tells us which scenario
we're in. If it turns out to be the random case, we can move straight
to MVP training; if systematic, we'd scope a targeted ingestion fix
into Phase 2 before retraining.

## What we'd need from you

To refine the demo into a Credit Cards MVP, the smallest viable input
set is:

1. **A sample data export** — ~30 days of historical credit-card clicks
joined to whatever sales data is available today. Schema and field
names are more useful than full volume; a 100 k-row sample is enough
to validate the join and run the coverage audit.

2. **The definition of a "conversion"** in your model — same-session
sale only, or multi-touch attributed? Time-to-conversion distribution
if you have it. Credit Cards has longer consideration windows than
typical e-commerce; we may want to extend the 30-day reconciliation
window we use today.

3. **The identifier that joins clicks to sales** — click ID,
correlation ID, or a hashed customer reference — and any caveats
about cross-device or offline conversions.

4. **An estimate of monthly Credit Card click volume** — drives Vertex
AI sizing and the cost line for prod.

5. **Confirmation on regulatory framing** — predicting click value
(not creditworthiness or offered terms) likely sits outside the FCA
boundaries that govern decisioning models, but worth a short note from
your compliance contact so we're aligned.

6. **Two named contacts on your side** — one data owner, one
engineering lead — so we can keep the working sessions tight.

Everything else (architecture, deployment, the prediction service,
the dashboard, the safety net, the explainability) is already
operational on staging and shipped in today's demo. The MVP work is
80% data and 20% model.

## How the 80% milestone fits

The platform is designed to retrain and canary-deploy without
downtime. The natural plan is:

- **Now → end of June.** Train v1 on the 50% sample, ship it behind a
canary, monitor calibration against the live reconciliation pipeline
you saw in the demo. Treat this as a learning environment, not a
production bidding signal.
- **End of June.** Coverage steps up to 80%. We retrain v2 on the
fuller dataset, traffic-split it against v1 (10% → 100% over a
couple of days), and the model-health dashboard tracks which version
served each click and what residuals look like for each.
- **End of July.** Cut over fully to v2 and decommission v1.

This is exactly the canary path the platform was built to do; the
80% milestone is a feature, not a hurdle.

## On the other points

- **Earlier Car Insurance work.** Looking forward to your follow-up
tomorrow. Agreed it's worth separating product-specific quirks from
anything structural before we lock the MVP scope.
- **Call next week.** Happy to. Suggest 60 minutes. I can prepare a
short pre-read with the data audit checklist and the v1/v2 milestone
plan above so we use the time on questions and trade-offs rather than
exposition. Send me two or three slots and I'll confirm.
- **Cloud questions with Ben.** No rush — they'll feed straight into
the prod-environment shape, so the sooner they're back the sooner we
can size the prod Vertex endpoint accurately. But Phase 1 doesn't
block on them.
- **Broader introductions.** Understood. Aligning on the MVP plan
first is the right sequence; intros are more useful once there's a
concrete artefact to discuss.

Look forward to picking this up next week.
