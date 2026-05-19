"""Generate docs/client-demo-deck.pptx — client-facing demo deck for the
Predictive RPC Estimator.

Audience: client executive + technical stakeholders attending the
solution demo. Tone: outcome-led, confident, light on internal jargon.

Idempotent: re-run to regenerate.
"""
from __future__ import annotations
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

OUT = Path(__file__).parent / "client-demo-deck.pptx"
DEMO_URL = "https://dashboard-staging-794974391956.europe-west2.run.app"
API_URL  = "https://scoring-api-staging-794974391956.europe-west2.run.app"

# Palette — calm, executive
NAVY   = RGBColor(0x0B, 0x1F, 0x3A)
TEAL   = RGBColor(0x0F, 0x6E, 0x7A)
SLATE  = RGBColor(0x33, 0x3F, 0x52)
LIGHT  = RGBColor(0xF4, 0xF6, 0xFA)
ACCENT = RGBColor(0xD9, 0x73, 0x06)
GREEN  = RGBColor(0x1F, 0x8A, 0x4F)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
MUTED  = RGBColor(0x6B, 0x73, 0x80)
RULE   = RGBColor(0xD7, 0xDB, 0xE3)

FONT = "Calibri"
TOTAL_PAGES = 11


def run(p, text, size=14, bold=False, color=SLATE, font=FONT, italic=False):
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font
    r.font.color.rgb = color
    return r


def fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def line(slide, x1, y1, x2, y2, color=RULE, weight=0.75):
    ln = slide.shapes.add_connector(1, x1, y1, x2, y2)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    return ln


def title_bar(slide, prs, title, eyebrow=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.0))
    fill(bar, NAVY)
    tf = bar.text_frame
    tf.margin_left = Inches(0.6); tf.margin_top = Inches(0.18)
    tf.word_wrap = True
    if eyebrow:
        p = tf.paragraphs[0]
        run(p, eyebrow.upper(), size=10, bold=True, color=ACCENT)
        p2 = tf.add_paragraph()
        run(p2, title, size=24, bold=True, color=WHITE)
    else:
        p = tf.paragraphs[0]
        run(p, title, size=26, bold=True, color=WHITE)
    # accent underline
    acc = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.95),
                                 Inches(1.2), Pt(3))
    fill(acc, ACCENT)


def footer(slide, prs, page_num, label="Predictive RPC Estimator — Client Demo"):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, prs.slide_height - Inches(0.35),
        prs.slide_width, Inches(0.35),
    )
    fill(bar, LIGHT)
    tf = bar.text_frame
    tf.margin_left = Inches(0.6); tf.margin_top = Inches(0.06)
    p = tf.paragraphs[0]
    run(p, f"{label}", size=9, color=MUTED)
    # right-aligned page number
    pn = slide.shapes.add_textbox(
        prs.slide_width - Inches(1.2), prs.slide_height - Inches(0.34),
        Inches(1.0), Inches(0.3),
    )
    pp = pn.text_frame.paragraphs[0]
    pp.alignment = PP_ALIGN.RIGHT
    run(pp, f"{page_num} / {TOTAL_PAGES}", size=9, color=MUTED)


def body_box(slide, prs, lines, top=Inches(1.25), left=Inches(0.6),
             width=None, height=None, font_size=14, line_spacing=1.2):
    width = width or prs.slide_width - Inches(1.2)
    height = height or prs.slide_height - Inches(1.7)
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame; tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = line_spacing
        if isinstance(ln, tuple):
            kind = ln[0]
            if kind == "h":
                run(p, ln[1], size=font_size + 4, bold=True, color=TEAL)
                p.space_after = Pt(6)
            elif kind == "b":
                run(p, "•  ", size=font_size, bold=True, color=ACCENT)
                run(p, ln[1], size=font_size, color=SLATE)
                p.space_after = Pt(3)
            elif kind == "sub":
                run(p, "    – ", size=font_size - 1, color=MUTED)
                run(p, ln[1], size=font_size - 1, color=SLATE)
            elif kind == "p":
                run(p, ln[1], size=font_size, color=SLATE)
                p.space_after = Pt(6)
            elif kind == "mute":
                run(p, ln[1], size=font_size - 2, color=MUTED, italic=True)
        else:
            run(p, ln, size=font_size, color=SLATE)
    return box


def metric_card(slide, left, top, w, h, value, label, value_color=NAVY, accent=TEAL):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    card.adjustments[0] = 0.06
    fill(card, WHITE)
    card.line.color.rgb = RULE
    card.line.width = Pt(0.75)
    # accent stripe
    stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, w, Inches(0.08))
    fill(stripe, accent)
    # value
    vb = slide.shapes.add_textbox(left, top + Inches(0.25), w, Inches(0.7))
    vp = vb.text_frame.paragraphs[0]; vp.alignment = PP_ALIGN.CENTER
    run(vp, value, size=28, bold=True, color=value_color)
    # label
    lb = slide.shapes.add_textbox(left, top + Inches(0.95), w, Inches(0.5))
    lp = lb.text_frame.paragraphs[0]; lp.alignment = PP_ALIGN.CENTER
    lp.line_spacing = 1.1
    run(lp, label, size=11, color=MUTED)

# ───────────────────────── Slides ─────────────────────────

def slide_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    fill(bg, NAVY)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(4.5),
                              prs.slide_width, Inches(0.08))
    fill(band, ACCENT)

    eyebrow = s.shapes.add_textbox(Inches(0.7), Inches(1.6), Inches(11), Inches(0.4))
    p = eyebrow.text_frame.paragraphs[0]
    run(p, "PREDICTIVE REVENUE INTELLIGENCE — CREDIT CARDS MVP",
        size=12, bold=True, color=ACCENT)

    title = s.shapes.add_textbox(Inches(0.7), Inches(2.1), Inches(11), Inches(1.4))
    tf = title.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    run(p, "Predictive RPC Estimator", size=44, bold=True, color=WHITE)
    p2 = tf.add_paragraph()
    run(p2, "Real-time revenue-per-click forecasting for Credit Cards",
        size=20, color=LIGHT)

    sub = s.shapes.add_textbox(Inches(0.7), Inches(4.8), Inches(11), Inches(2))
    tf = sub.text_frame; tf.word_wrap = True
    for label, val in [
        ("Solution demo", "Live staging environment"),
        ("Audience", "Credit Cards leadership + technical stakeholders"),
        ("Date", "2026-05-19"),
    ]:
        p = tf.add_paragraph(); p.line_spacing = 1.3
        run(p, f"{label}    ", size=12, bold=True, color=ACCENT)
        run(p, val, size=14, color=WHITE)
    p = tf.add_paragraph(); p.line_spacing = 1.5
    run(p, " ", size=8)
    p = tf.add_paragraph()
    run(p, "Live dashboard:  ", size=11, bold=True, color=ACCENT)
    run(p, DEMO_URL, size=11, color=LIGHT)


def slide_opportunity(prs):
    """Folds the previous Exec Summary + Opportunity into one tight slide.
    Business framing first, with the 50%→80% trajectory pinned."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "The opportunity — Credit Cards, now",
              eyebrow="Why this vertical, why this quarter")
    body_box(s, prs, [
        ("h", "Flat target-CPA wastes spend on the clicks that matter most."),
        ("p", "Every Credit Cards click is priced the same. The whales — high-value applicants who'd convert at 3× the bid — are under-paid for and lost to rivals. The minnows are over-paid for. You only see the cost 90 days later when the ledger reconciles."),
        ("h", "Why Credit Cards, why now"),
        ("b", "Near-term commercial pressure on the channel — first vertical to repay the platform investment."),
        ("b", "Sales coverage rising 50% → 80% by end-June; the model retrains and canary-deploys as coverage climbs."),
        ("b", "Lower regulatory risk than Car Insurance: bid-optimisation only, no customer-decisioning surface — the FCA boundary is enforced in the platform (ADR 0004)."),
        ("h", "What a predictive bid layer changes"),
        ("b", "Bid the click likely to convert, not the click that already did."),
        ("b", "Detect campaign degradation before it shows up in revenue — per-segment drift alerts week-over-week."),
        ("b", "Explain every prediction in plain English — auditable for finance and compliance."),
    ], font_size=13)
    footer(s, prs, 2)


def slide_what_we_built(prs):
    """Solution + deliverables folded. One slide showing the surfaces
    + what's running underneath."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "What we've built", eyebrow="Live on Google Cloud staging today")

    # Left column — what the audience interacts with
    body_box(s, prs, [
        ("h", "Surfaces (what you see)"),
        ("b", "Executive dashboard — KPIs in £, 90-day default, product-type filter, coverage-audit panel, active-versions panel."),
        ("b", "Hero before/after — same click, flat-tCPA vs value-based bid vs the £ difference, with a running session counter."),
        ("b", "Phoebe journey — animated 6-step replay of a user's intent building up, with the bid following it."),
        ("b", "Live prediction card — CC-shaped form; plain-English SHAP explanation under every prediction."),
        ("b", "Designed-against tile — three common failure modes, mapped to the platform mitigation."),
        ("b", "REST API — same predictions for SA360 / SSGTM / OCI."),
    ], top=Inches(1.25), left=Inches(0.55), width=Inches(6.2), font_size=11)

    # Right column — what's running underneath
    body_box(s, prs, [
        ("h", "Underneath (what's running)"),
        ("b", "scoring-api (Rust on Cloud Run) — p95 < 1 second, kill-switch flag, circuit breaker, bounds → fallback."),
        ("b", "Vertex AI online endpoint — XGBoost regressor, native SHAP explainability, canary traffic-split for rollout."),
        ("b", "Reconciliation — BigQuery view joins predictions to the 90-day sales ledger; coverage_audit slices the gaps."),
        ("b", "Dataform: phoebe_features, residuals_by_segment, drift_breaches_weekly, coverage_drops_weekly."),
        ("b", "Drift + coverage-drop alerts — Cloud Monitoring policies fire on the dimensions that matter for CC."),
        ("b", "CD: tag push → build → push → terraform apply → smoke. Rollback is a single Vertex traffic-split."),
    ], top=Inches(1.25), left=Inches(6.95), width=Inches(6.2), font_size=11)

    # Bottom strip — env + URL
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                             Inches(0.55), Inches(6.55),
                             prs.slide_width - Inches(1.1), Inches(0.45))
    fill(bar, NAVY)
    tf = bar.text_frame
    tf.margin_left = Inches(0.18); tf.margin_top = Inches(0.10)
    p = tf.paragraphs[0]
    run(p, "europe-west2 (London)  ·  managed services only  ·  no client infrastructure to operate  ·  ",
        size=10, color=LIGHT)
    run(p, DEMO_URL, size=10, bold=True, color=ACCENT)
    footer(s, prs, 3)


def slide_architecture(prs):
    """Native-pptx 4-lane diagram tailored for Credit Cards. Replaces
    the V1 embedded PNG which doesn't show Phoebe / GA4, the per-segment
    drift path, or the breach scanner.
    """
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "End-to-end architecture",
              eyebrow="Credit Cards stack on Google Cloud")

    # 4 lanes, left to right
    lanes = [
        ("Sources", NAVY, [
            ("CM360 click stream", "Pub/Sub → BigQuery"),
            ("Sales ledger", "BigQuery, multi-stage events"),
            ("GA4 events (Phoebe)", "Daily BigQuery export"),
        ]),
        ("Real-time hot path", TEAL, [
            ("scoring-api (Rust, Cloud Run)", "p95 < 1s, /v1/score + /v1/explain"),
            ("Safety net", "Bounds, breaker, kill switch, anomaly window"),
            ("Vertex AI endpoint", "XGBoost + native SHAP"),
            ("Feature store", "Phoebe lookup at scoring time"),
        ]),
        ("Reconciliation + ML", ACCENT, [
            ("BigQuery views", "predictions_vs_revenue, coverage_audit"),
            ("Dataform", "residuals_by_segment, drift_breaches"),
            ("ml-pipeline", "Vertex Pipelines retrain on tag"),
            ("breach_emitter", "Daily scheduler → log → alerts"),
        ]),
        ("Surfaces + activation", GREEN, [
            ("Executive dashboard", "React + nginx on Cloud Run"),
            ("Activation API", "SA360 / SSGTM / OCI push"),
            ("Cloud Monitoring", "6 alert policies → on-call"),
        ]),
    ]

    n = len(lanes)
    margin = Inches(0.4)
    avail_w = prs.slide_width - Inches(0.8)
    lane_w = (avail_w - margin * (n - 1)) / n
    top = Inches(1.20)
    lane_h = Inches(5.55)

    for i, (lane_title, accent, items) in enumerate(lanes):
        x = Inches(0.4) + i * (lane_w + margin)

        # Lane card
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, lane_w, lane_h)
        card.adjustments[0] = 0.04
        fill(card, WHITE)
        card.line.color.rgb = RULE; card.line.width = Pt(0.75)

        # Header stripe
        stripe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, lane_w, Inches(0.5))
        fill(stripe, accent)
        hb = s.shapes.add_textbox(x + Inches(0.15), top + Inches(0.06),
                                  lane_w - Inches(0.3), Inches(0.4))
        p = hb.text_frame.paragraphs[0]
        run(p, lane_title.upper(), size=11, bold=True, color=WHITE)

        # Items
        item_top = top + Inches(0.65)
        item_h = Inches(1.1)
        item_gap = Inches(0.12)
        for j, (label, sub) in enumerate(items):
            iy = item_top + j * (item_h + item_gap)
            ic = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   x + Inches(0.15), iy,
                                   lane_w - Inches(0.3), item_h)
            ic.adjustments[0] = 0.10
            fill(ic, LIGHT)
            ic.line.color.rgb = RULE; ic.line.width = Pt(0.5)
            tf = ic.text_frame
            tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.10)
            tf.margin_top = Inches(0.12); tf.margin_bottom = Inches(0.08)
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run(p, label, size=11, bold=True, color=NAVY)
            p2 = tf.add_paragraph(); p2.line_spacing = 1.15
            run(p2, sub, size=9, color=SLATE)

        # Arrow to next lane
        if i < n - 1:
            arrow_x1 = x + lane_w + Pt(2)
            arrow_x2 = x + lane_w + margin - Pt(2)
            arrow_y = top + lane_h / 2
            ln = s.shapes.add_connector(2, arrow_x1, arrow_y, arrow_x2, arrow_y)
            ln.line.color.rgb = MUTED; ln.line.width = Pt(2)

    footer(s, prs, 4)


def slide_demo_walkthrough(prs):
    """Seven-beat walkthrough matching what's on the dashboard now.
    Two-column layout so it fits at 11pt body."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Live demo — what you will see",
              eyebrow="Seven beats, one URL")

    left_col = [
        ("h", "1. KPIs + product-type filter"),
        ("p", "Five KPIs in £; 90-day default window; product-type filter re-segments the chart instantly."),
        ("h", "2. Coverage panel"),
        ("p", "Bar chart per product slice; red bars are slices below 60% — the slices that need ingestion backfill before retraining. This is how we answer the 50% question, slice by slice."),
        ("h", "3. Hero before/after"),
        ("p", "Same click, three cards: flat tCPA target, value-based bid (predicted RPC × bid efficiency), the £ difference. Session counter accumulates across every prediction the audience fires."),
        ("h", "4. Live prediction card"),
        ("p", "Form in CC language — product type, calculator used, guides read, cards compared, time engaged. Press Predict — pipeline trace lights up live: validate → guardrails → Vertex → BigQuery → SHAP."),
    ]
    right_col = [
        ("h", "5. Phoebe journey — bouncer with a crystal ball"),
        ("p", "Press Play. A user moves through six steps (search → page → calculator → guides → compare-5 → click). The bid ticks up under each step. A lift pill shows the £ delta from first to last."),
        ("h", "6. Why the model said that"),
        ("p", "Horizontal-bar SHAP attribution under every prediction. Plain-English names. Auditable for finance and compliance — ADR 0004 blocks these signals from reaching customer terms."),
        ("h", "7. Designed-against + verticals roadmap"),
        ("p", "Three failure modes named on screen, each mapped to where the platform pushes back. Five-vertical roadmap: CC live, Loans next, then Home / Life / Mortgages."),
        ("mute", f"Live dashboard  ·  {DEMO_URL}"),
    ]
    body_box(s, prs, left_col,
             top=Inches(1.25), left=Inches(0.55),
             width=Inches(6.2), font_size=11, line_spacing=1.15)
    body_box(s, prs, right_col,
             top=Inches(1.25), left=Inches(6.95),
             width=Inches(6.2), font_size=11, line_spacing=1.15)
    footer(s, prs, 5)


def slide_tech_choices(prs):
    """The 'why this stack' slide. Pre-empts CTO-room defaults questions."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Why these technology choices",
              eyebrow="What we evaluated, and what we chose")

    left_col = [
        ("h", "Hot path — Rust on Cloud Run"),
        ("b", "Latency budget: p95 ≤ 1.5 s end-to-end; Vertex AI predict dominates ~700 ms. Rust leaves the rest for the safety-net with zero GC jitter."),
        ("b", "Considered Go and Python; both leave less headroom and complicate the breaker's idempotency."),
        ("h", "Model — XGBoost on Vertex AI"),
        ("b", "Feature space is tabular, ~11 columns. GBDT is the empirical leader for tabular regression at this scale."),
        ("b", "Native SHAP via Vertex explanationSpec — /v1/explain is free; deep models need a separate KernelSHAP that's harder to audit under ADR 0004."),
        ("b", "Deterministic predict composes with the circuit breaker; transformers' stateful decoding would not."),
        ("h", "Frontend — TypeScript + React + Vite"),
        ("b", "Single URL with realtime interactivity (live prediction, Phoebe journey). Zod validates JSON at the boundary."),
    ]
    right_col = [
        ("h", "Contracts — Protobuf"),
        ("b", "Wire stability across Rust ↔ Python; codegen per language; CI parity test guards drift."),
        ("h", "Data layer — Dataform on BigQuery"),
        ("b", "Same primitives as dbt; one less tool the client must install. Type-safe ref()s give us the dependency graph automatically."),
        ("h", "Identity — Workload Identity Federation"),
        ("b", "GitHub OIDC federates into GCP. No long-lived service-account keys to rotate or leak."),
        ("b", "Per-service service accounts; every IAM grant in Terraform — reviewable in git, not in the console."),
        ("h", "Runtime — Cloud Run"),
        ("b", "Request-driven autoscaling; min=1 keeps demo warm at ~£3–5/day; ramps under load without paging us."),
        ("b", "Considered GKE — overkill for a stateless CPU-bound service; we'd pay cluster overhead we don't use."),
    ]
    body_box(s, prs, left_col,
             top=Inches(1.20), left=Inches(0.5),
             width=Inches(6.2), font_size=10, line_spacing=1.15)
    body_box(s, prs, right_col,
             top=Inches(1.20), left=Inches(6.85),
             width=Inches(6.2), font_size=10, line_spacing=1.15)
    footer(s, prs, 6)


def slide_engineering(prs):
    """Folds previous Engineering + Security + Operability into one
    production-grade slide. The 'we know how to run this' answer."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Production-grade engineering",
              eyebrow="What runs underneath the demo")

    left_col = [
        ("h", "Reliability"),
        ("b", "Bounds → flat-tCPA fallback on every prediction."),
        ("b", "Circuit breaker on the model endpoint; auto-recover when healthy."),
        ("b", "Anomaly window on null-rates flips a single kill-switch flag — no redeploy."),
        ("b", "Per-call timeouts on model + warehouse — no request hangs."),
        ("h", "Observability"),
        ("b", "Cloud Logging + Trace + Monitoring out of the box."),
        ("b", "Six alert policies: latency p95, 5xx rate, breaker trips, anomaly state, per-segment MAE drift > 25% W-o-W, coverage drop > 10pp W-o-W."),
        ("b", "Service-level objective: 99.5% availability on /v1/score, 30-day rolling."),
    ]
    right_col = [
        ("h", "Security + compliance"),
        ("b", "Per-service service accounts; least-privilege IAM in Terraform — every grant is reviewable in git."),
        ("b", "Workload Identity Federation — no long-lived secrets in CI."),
        ("b", "Secret Manager with versioning; rotation is a runbooked one-liner."),
        ("b", "ADR 0004 — bid-optimisation boundary: no customer identifiers in; no output reaches anything that affects customer terms."),
        ("b", "ADR 0005 — GA4 / Phoebe PII boundary: hashed user_pseudo_id only; raw user_id and PII params stripped at the staging view."),
        ("h", "Operability"),
        ("b", "Tag-push CI → CD → smoke; rollback is a Vertex traffic-split."),
        ("b", "Runbooks committed: breaker reset, model rollback, secret rotation, coverage audit, BQ schema migration, endpoint scale-down."),
    ]
    body_box(s, prs, left_col,
             top=Inches(1.20), left=Inches(0.55),
             width=Inches(6.2), font_size=11, line_spacing=1.15)
    body_box(s, prs, right_col,
             top=Inches(1.20), left=Inches(6.95),
             width=Inches(6.2), font_size=11, line_spacing=1.15)
    footer(s, prs, 7)


def slide_data_model(prs):
    """CC schema + Phoebe + reconciliation + drift in one slide."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Data and model lifecycle",
              eyebrow="From your ledger to a live prediction")
    body_box(s, prs, [
        ("h", "Three feeds, one model"),
        ("b", "Click stream (CM360, CC schema): product_type, card_product_id, query_intent, affinity_score, prior_applicant, income_band_bucket, rpc_14d/60d."),
        ("b", "Sales ledger: multi-stage events (application_started → submitted → approved → activated → first_spend → chargeback) with revenue, margin_rate (profit-ready), card_product_id, currency."),
        ("b", "GA4 / Phoebe: per-cookie 30-day rollup — calculator_used, guides_read, cards_compared, session_engagement_s. Joined at training; looked up at serving."),
        ("h", "Label and reconciliation window"),
        ("b", "Sum-of-rewards over a 90-day window (ADR 0003 — fits the CC consideration tail). Profit-ready label: SUM(revenue × COALESCE(margin_rate, 1.0))."),
        ("h", "Training and release"),
        ("b", "Vertex AI Pipelines run from the same monorepo — reproducible from a commit. Every version in the Vertex Model Registry."),
        ("b", "Canary 10% → 50% over 48h → 100%. Active-versions panel shows the share and rolling MAE side-by-side."),
        ("h", "Drift, four ways"),
        ("b", "Inputs (PSI per feature); outputs (residuals_daily); per-segment MAE (product × device × geo); coverage drop W-o-W per slice."),
        ("mute", "Today's model is trained on synthetic data mirroring the CC schema. First work item once OQ-11 (GA4 access) and the data contract land is retrain on real."),
    ], font_size=11)
    footer(s, prs, 8)


def slide_roadmap(prs):
    """Three phase cards, tightened so text fits inside 4.0" height."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Delivery roadmap", eyebrow="From here to cutover")

    phases = [
        ("Phase 1", "Platform & schema",
         "Complete", GREEN, [
            "CC schema end-to-end",
            "Phoebe features wired",
            "Demo dashboard live",
            "Drift + coverage alerts",
        ]),
        ("Phase 2", "Real data",
         "Pending client", ACCENT, [
            "GA4 access (OQ-11)",
            "Sample data export",
            "v1 on 50% coverage",
            "Canary 10% → 100%",
        ]),
        ("Phase 3", "Cutover",
         "End-August 2026", TEAL, [
            "v2 on 80% coverage",
            "Rollback rehearsed",
            "ADR 0004 / 0005 sign-off",
            "Handover to on-call",
        ]),
    ]
    cw = Inches(4.05); ch = Inches(4.20); top = Inches(1.30)
    left0 = Inches(0.55); gap = Inches(0.25)
    for i, (phase, title, status, color, items) in enumerate(phases):
        x = left0 + i * (cw + gap)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, cw, ch)
        card.adjustments[0] = 0.05
        fill(card, WHITE)
        card.line.color.rgb = RULE; card.line.width = Pt(0.75)
        # Header stripe
        stripe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, cw, Inches(0.55))
        fill(stripe, color)
        hb = s.shapes.add_textbox(x + Inches(0.2), top + Inches(0.07),
                                  cw - Inches(0.4), Inches(0.5))
        p = hb.text_frame.paragraphs[0]
        run(p, phase, size=11, bold=True, color=WHITE)
        p2 = hb.text_frame.add_paragraph()
        run(p2, title, size=15, bold=True, color=WHITE)
        # Status pill
        sb = s.shapes.add_textbox(x + Inches(0.2), top + Inches(0.72),
                                  cw - Inches(0.4), Inches(0.32))
        p = sb.text_frame.paragraphs[0]
        run(p, status.upper(), size=10, bold=True, color=color)
        # Items
        ib = s.shapes.add_textbox(x + Inches(0.25), top + Inches(1.15),
                                  cw - Inches(0.5), ch - Inches(1.30))
        tf = ib.text_frame; tf.word_wrap = True
        for j, it in enumerate(items):
            pp = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            pp.line_spacing = 1.25; pp.space_after = Pt(4)
            run(pp, "✓  " if status == "Complete" else "•  ",
                size=12, bold=True, color=color)
            run(pp, it, size=12, color=SLATE)

    note = s.shapes.add_textbox(Inches(0.55), Inches(5.70),
                                prs.slide_width - Inches(1.1), Inches(0.6))
    p = note.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run(p, "Timeline measured from data-sample arrival, not kickoff. "
        "Phase 2 starts the day GA4 access + a sample data export land.",
        size=10, italic=True, color=MUTED)
    footer(s, prs, 9)


def slide_commercials(prs):
    """What we need, in priority order. OQs named."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "What we need from you",
              eyebrow="Next steps to unlock value")
    body_box(s, prs, [
        ("h", "Five decisions — in priority order"),
        ("b", "OQ-11 · GA4 access. Read on the Credit Cards analytics_<property> BigQuery export. Critical-path: every week this slides is a week off the cutover."),
        ("b", "OQ-12 · GA4 event taxonomy. Confirm which event_name values map to 'calculator used', 'guide read', 'card compare'. One working session."),
        ("b", "OQ-13 · Click → cookie join key. Server-side CM360+GA4 merge, first-party cookie pass-through, or no-join. Decides whether Phoebe lifts the live model."),
        ("b", "OQ-1 · GCP project. Client's own, or a namespaced env in our msm-rpc project — the deploy-client-cc CD job is wired and gated on the decision."),
        ("b", "Compliance sign-off on ADRs 0004 (FCA boundary) and 0005 (GA4 PII). Two named contacts: one data owner + one engineering lead."),
        ("h", "What you also get"),
        ("b", "The Car Insurance failure summary from Ryan refines the 'designed against' tile from speculation to confirmed mitigations."),
        ("b", "Read-only access to the live staging environment for your team to probe."),
        ("h", "What you get at the end"),
        ("b", "A production service on your data, with your on-call team in the cockpit and a signed handover by end-August 2026."),
    ], font_size=12)
    footer(s, prs, 10)


def slide_thanks(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    fill(bg, NAVY)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(3.0),
                              prs.slide_width, Inches(0.08))
    fill(band, ACCENT)

    t = s.shapes.add_textbox(Inches(0.7), Inches(2.0), Inches(12), Inches(1.2))
    p = t.text_frame.paragraphs[0]
    run(p, "Questions?", size=54, bold=True, color=WHITE)

    sub = s.shapes.add_textbox(Inches(0.7), Inches(3.4), Inches(12), Inches(1.0))
    p = sub.text_frame.paragraphs[0]
    run(p, "Predictive RPC Estimator — Credit Cards MVP  ·  Live demo  ·  Q&A",
        size=18, color=LIGHT)

    foot = s.shapes.add_textbox(Inches(0.7), Inches(6.7), Inches(12), Inches(0.4))
    p = foot.text_frame.paragraphs[0]
    run(p, f"Live dashboard  ·  {DEMO_URL}", size=11, color=ACCENT)


def main():
    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_cover(prs)              # 1
    slide_opportunity(prs)        # 2
    slide_what_we_built(prs)      # 3
    slide_architecture(prs)       # 4
    slide_demo_walkthrough(prs)   # 5
    slide_tech_choices(prs)       # 6
    slide_engineering(prs)        # 7
    slide_data_model(prs)         # 8
    slide_roadmap(prs)            # 9
    slide_commercials(prs)        # 10
    slide_thanks(prs)             # 11

    prs.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
