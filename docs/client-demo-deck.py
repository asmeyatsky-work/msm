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
TOTAL_PAGES = 15


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

    eyebrow = s.shapes.add_textbox(Inches(0.7), Inches(1.6), Inches(9), Inches(0.4))
    p = eyebrow.text_frame.paragraphs[0]
    run(p, "PREDICTIVE REVENUE INTELLIGENCE", size=12, bold=True, color=ACCENT)

    title = s.shapes.add_textbox(Inches(0.7), Inches(2.1), Inches(9), Inches(1.4))
    tf = title.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    run(p, "Predictive RPC Estimator", size=44, bold=True, color=WHITE)
    p2 = tf.add_paragraph()
    run(p2, "Real-time revenue-per-click forecasting on Google Cloud",
        size=20, color=LIGHT)

    sub = s.shapes.add_textbox(Inches(0.7), Inches(4.8), Inches(9), Inches(2))
    tf = sub.text_frame; tf.word_wrap = True
    for label, val in [
        ("Solution demo", "Live staging environment"),
        ("Audience", "Client executive and technical stakeholders"),
        ("Date", "2026-05-11"),
    ]:
        p = tf.add_paragraph(); p.line_spacing = 1.3
        run(p, f"{label}    ", size=12, bold=True, color=ACCENT)
        run(p, val, size=14, color=WHITE)
    p = tf.add_paragraph(); p.line_spacing = 1.5
    run(p, " ", size=8)
    p = tf.add_paragraph()
    run(p, "Live dashboard:  ", size=11, bold=True, color=ACCENT)
    run(p, DEMO_URL, size=11, color=LIGHT)


def slide_exec_summary(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Executive summary", eyebrow="Where we are today")
    body_box(s, prs, [
        ("h", "A production-grade revenue forecasting service is operational."),
        ("p", "We have built and deployed an end-to-end machine-learning service that predicts revenue-per-click in real time, with the engineering controls required to run it safely in production."),
        ("h", "Three things to take away today"),
        ("b", "Working software — a live API on Google Cloud is serving predictions right now, with measured p95 latency under one second."),
        ("b", "Production engineering — circuit breakers, drift monitoring, explainability, alerting, runbooks, and a tested rollback path are all in place."),
        ("b", "A clear path to your data — the platform is ready to ingest real click and sales-ledger feeds; the model retrains and canary-deploys without downtime."),
    ], font_size=14)
    footer(s, prs, 2)


def slide_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "The opportunity", eyebrow="Why this matters")
    body_box(s, prs, [
        ("h", "Bidding and budget decisions today rely on lagging signals."),
        ("p", "Revenue per click is reconciled days after the fact, from a sales ledger that lives apart from the ad platforms making spend decisions. By the time the numbers settle, the budget has already been committed."),
        ("h", "What a predictive RPC unlocks"),
        ("b", "Bid the click that's likely to convert — not the click that already did."),
        ("b", "Reallocate spend within the hour, not the week."),
        ("b", "Detect campaign degradation before it shows up in revenue."),
        ("b", "Explain every prediction — auditability for finance and compliance."),
    ], font_size=14)
    footer(s, prs, 3)


def slide_solution(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Solution overview", eyebrow="What we have built")
    body_box(s, prs, [
        ("h", "A managed prediction service on Google Cloud."),
        ("b", "REST API — POST a click context, receive an RPC estimate in under a second."),
        ("b", "Explainability — every prediction can return per-feature attributions so analysts can see why the model said what it said."),
        ("b", "Streaming ingestion — predictions land in BigQuery for analytics, reconciliation, and downstream activation."),
        ("b", "Safety net — anomaly detection, automatic circuit-breaker, negative-prediction guards, configurable timeouts."),
        ("b", "One-command deploys — every change ships through CI with a tested rollback to the prior model version."),
        ("h", " "),
        ("mute", "All components run in Google Cloud (europe-west2, London) on managed services — Cloud Run, Vertex AI, BigQuery, Pub/Sub — so there is no infrastructure for the client team to operate."),
    ], font_size=14)
    footer(s, prs, 4)


def slide_deliverables(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Deliverables and audience",
              eyebrow="What you receive, who consumes it")

    rows = [
        ("dashboard/  (React + nginx)",
         "Executive UI",
         "Yes — primary demo",
         "primary"),
        ("scoring-api  /v1/score, /v1/explain",
         "Their backend / SA360 integration",
         "API only — show via curl / Postman on slide 7",
         "api"),
        ("reconciliation  /reconciliation",
         "Powers the dashboard",
         "API only — invisible to client",
         "api"),
        ("activation",
         "SA360 / SSGTM push",
         "Backend, no UI",
         "backend"),
        ("breaker-automation, ml-pipeline, bounds-calibration",
         "Internal / scheduled",
         "Backend",
         "backend"),
        ("mcp-servers/scoring-mcp, mlops-mcp",
         "Agent tooling for engineers",
         "Not client-facing",
         "backend"),
        ("Dataform models, BigQuery views",
         "Analyst layer",
         "Available in Looker Studio as a second visual artefact (optional)",
         "optional"),
    ]

    # Layout
    top    = Inches(1.25)
    left   = Inches(0.5)
    width  = prs.slide_width - Inches(1.0)
    header_h = Inches(0.45)
    row_h    = Inches(0.55)
    col_w = [Inches(4.6), Inches(3.4), width - Inches(4.6) - Inches(3.4)]

    # Header
    hx = left
    for i, label in enumerate(["What", "Audience", "Client-facing?"]):
        cell = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, hx, top, col_w[i], header_h)
        fill(cell, NAVY)
        tf = cell.text_frame
        tf.margin_left = Inches(0.18); tf.margin_top = Inches(0.08)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        run(p, label.upper(), size=10, bold=True, color=WHITE)
        hx += col_w[i]

    # Body
    badge_color = {
        "primary":  GREEN,
        "api":      TEAL,
        "backend":  MUTED,
        "optional": ACCENT,
    }

    y = top + header_h
    for idx, (what, audience, client, kind) in enumerate(rows):
        # zebra background
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, y, width, row_h)
        fill(bg, LIGHT if idx % 2 == 0 else WHITE)
        bg.line.color.rgb = RULE
        bg.line.width = Pt(0.5)

        # Left accent stripe coloured by row kind
        stripe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, y, Inches(0.06), row_h)
        fill(stripe, badge_color[kind])

        # Column 1 — What
        c1 = s.shapes.add_textbox(left + Inches(0.18), y, col_w[0] - Inches(0.18), row_h)
        c1.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c1.text_frame.paragraphs[0]
        run(p, what, size=11, bold=True, color=NAVY, font="Consolas")

        # Column 2 — Audience
        c2 = s.shapes.add_textbox(left + col_w[0], y, col_w[1], row_h)
        c2.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = c2.text_frame.paragraphs[0]
        run(p, audience, size=11, color=SLATE)

        # Column 3 — Client-facing (with leading dot)
        c3 = s.shapes.add_textbox(left + col_w[0] + col_w[1], y, col_w[2], row_h)
        c3.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        c3.text_frame.word_wrap = True
        p = c3.text_frame.paragraphs[0]
        run(p, "● ", size=11, bold=True, color=badge_color[kind])
        run(p, client, size=11,
            bold=(kind == "primary"),
            color=(NAVY if kind == "primary" else SLATE))

        y += row_h

    # Footnote
    note = s.shapes.add_textbox(left, y + Inches(0.12), width, Inches(0.5))
    p = note.text_frame.paragraphs[0]
    run(p,
        "Nothing else in the repository is a runnable demo. The dashboard plus a handful of API "
        "calls against the scoring service is the complete client-facing surface.",
        size=10, italic=True, color=MUTED)

    footer(s, prs, 6)


def slide_architecture(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "How it works", eyebrow="Architecture, in one picture")

    # Simple lane diagram
    y0 = Inches(1.35)
    lane_h = Inches(1.3)

    # Lane 1: client → scoring api → vertex
    def node(slide, left, top, w, h, label, sublabel="", color=TEAL, text_color=WHITE):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
        box.adjustments[0] = 0.15
        fill(box, color)
        tf = box.text_frame; tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run(p, label, size=13, bold=True, color=text_color)
        if sublabel:
            p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
            run(p2, sublabel, size=9, color=LIGHT if text_color == WHITE else MUTED)

    def arrow(slide, x1, y1, x2, y2):
        con = slide.shapes.add_connector(3, x1, y1, x2, y2)  # straight
        con.line.color.rgb = SLATE
        con.line.width = Pt(1.5)

    nw, nh = Inches(1.7), Inches(0.9)
    row1_y = Inches(1.6)
    gap = Inches(0.35)

    node(s, Inches(0.5), row1_y, nw, nh, "Client app", "browser / server", color=SLATE)
    node(s, Inches(0.5) + nw + gap, row1_y, nw, nh, "Scoring API",
         "Cloud Run · Rust", color=TEAL)
    node(s, Inches(0.5) + 2 * (nw + gap), row1_y, nw, nh, "Vertex AI",
         "XGBoost regressor", color=NAVY)
    node(s, Inches(0.5) + 3 * (nw + gap), row1_y, nw, nh, "Pub/Sub",
         "predictions stream", color=ACCENT, text_color=WHITE)
    node(s, Inches(0.5) + 4 * (nw + gap), row1_y, nw, nh, "BigQuery",
         "analytics + drift", color=TEAL)

    # arrows between row1 nodes
    for i in range(4):
        x1 = Inches(0.5) + (i + 1) * nw + i * gap
        x2 = x1 + gap
        y  = row1_y + Emu(int(nh / 2))
        arrow(s, x1, y, x2, y)

    # Row 2 — guardrails caption
    cap = s.shapes.add_textbox(Inches(0.5), Inches(2.9),
                               prs.slide_width - Inches(1.0), Inches(0.45))
    p = cap.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run(p, "Each request is wrapped in production safety controls",
        size=11, italic=True, color=MUTED)

    # Row 3: guardrails
    guards = [
        ("Timeouts", "model + BQ budgets"),
        ("Circuit breaker", "fail fast, recover"),
        ("Anomaly detection", "null-rate window"),
        ("Range clamp", "no negative RPC"),
        ("Explanations", "per-feature SHAP"),
    ]
    gw = Inches(1.7); gy = Inches(3.45); gh = Inches(0.9)
    gap2 = Inches(0.15)
    for i, (lbl, sub) in enumerate(guards):
        node(s, Inches(0.5) + i * (gw + gap2), gy, gw, gh, lbl, sub,
             color=LIGHT, text_color=NAVY)

    # Bottom note
    note = s.shapes.add_textbox(Inches(0.5), Inches(4.7),
                                prs.slide_width - Inches(1.0), Inches(1.2))
    tf = note.text_frame; tf.word_wrap = True
    for txt in [
        ("h", "Why this shape"),
        ("b", "Stateless API tier scales horizontally with traffic — pay only for what you use."),
        ("b", "Vertex AI hosts the model, so retraining and versioning never touch the API."),
        ("b", "Every prediction is captured in BigQuery — same dataset your analysts already use."),
    ]:
        kind, t = txt
        p = tf.add_paragraph() if tf.text else tf.paragraphs[0]
        if kind == "h":
            run(p, t, size=14, bold=True, color=TEAL)
            p.space_after = Pt(3)
        else:
            run(p, "•  ", size=12, bold=True, color=ACCENT)
            run(p, t, size=12, color=SLATE)
    footer(s, prs, 5)


def slide_demo_script(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Live demo — what you will see",
              eyebrow="Five minutes, three screens")
    body_box(s, prs, [
        ("h", "1.  The reconciliation dashboard"),
        ("p", "We open the live dashboard. It shows the last seven days of predictions paired with realized revenue from the sales ledger — predicted RPC, realized RPC, residual, and which model branch served each click."),
        ("h", "2.  A prediction in flight"),
        ("p", "We send a sample click context to the live scoring API and receive an RPC estimate, end-to-end, in under a second. The same input is then sent to the explain path to show per-feature attributions."),
        ("h", "3.  The safety net in action"),
        ("p", "We send a deliberately malformed payload. The service rejects it cleanly, the circuit-breaker counters tick, and the request never reaches the model. No degradation visible to clean traffic."),
        ("mute", f"Dashboard  ·  {DEMO_URL}"),
        ("mute", f"Scoring API  ·  {API_URL}"),
    ], font_size=14)
    footer(s, prs, 7)


def slide_performance(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Measured performance", eyebrow="Load test, live staging")
    # 4 metric cards
    cw = Inches(2.15); ch = Inches(1.55); top = Inches(1.35)
    left0 = Inches(0.6); gap = Inches(0.2)
    metric_card(s, left0 + 0 * (cw + gap), top, cw, ch, "561 ms", "Median (p50) /v1/score")
    metric_card(s, left0 + 1 * (cw + gap), top, cw, ch, "762 ms", "p95 /v1/score",
                accent=GREEN)
    metric_card(s, left0 + 2 * (cw + gap), top, cw, ch, "993 ms", "p99 /v1/score")
    metric_card(s, left0 + 3 * (cw + gap), top, cw, ch, "100 %", "Success rate",
                value_color=GREEN, accent=GREEN)

    body_box(s, prs, [
        ("h", "Headroom against the SLO"),
        ("b", "Staging p95 latency budget is 1500 ms — observed 762 ms leaves roughly a 2× margin before alerts fire."),
        ("b", "Zero errors at the tested rate; prior runs showed the service recovers cleanly under autoscaling load."),
        ("b", "Production sizing has been pre-computed from these numbers — a larger Vertex machine and a minimum of two replicas keep the same headroom under client traffic."),
        ("mute", "Source: ops/perf/20260428T094507Z__v1_score.json  ·  tool: oha, 30s @ c=10  ·  europe-west2"),
    ], top=Inches(3.1), font_size=13)
    footer(s, prs, 8)


def slide_engineering(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Production-grade engineering",
              eyebrow="What runs underneath the demo")
    # two columns
    left_col = [
        ("h", "Reliability"),
        ("b", "Circuit-breaker on the upstream model — fails fast and recovers automatically."),
        ("b", "Configurable timeouts for model and warehouse calls — no request hangs indefinitely."),
        ("b", "Negative-prediction clamp and input validation at the edge."),
        ("b", "Anomaly window on null-rates flips the breaker before bad data reaches finance."),
    ]
    right_col = [
        ("h", "Operability"),
        ("b", "Every change ships through GitHub Actions on tag push, gated by tests, type checks, and security scan."),
        ("b", "Workload Identity Federation — no service-account keys to manage or rotate."),
        ("b", "Cloud Monitoring alerts on latency, error rate, breaker trips, and anomaly state."),
        ("b", "Runbooks committed for breaker reset, model rollback, secret rotation, and cost scale-down."),
    ]
    body_box(s, prs, left_col,
             top=Inches(1.25), left=Inches(0.6),
             width=Inches(6.0), font_size=13)
    body_box(s, prs, right_col,
             top=Inches(1.25), left=Inches(7.0),
             width=Inches(6.0), font_size=13)
    footer(s, prs, 9)


def slide_security(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Security and compliance posture",
              eyebrow="Built to pass review")
    body_box(s, prs, [
        ("h", "Identity and access"),
        ("b", "Per-service service accounts; least-privilege IAM encoded in Terraform — every grant is reviewable in git."),
        ("b", "No long-lived secrets in CI: GitHub OIDC federates into Google Cloud via Workload Identity."),
        ("b", "Secrets in Secret Manager with versioning; rotation is a runbooked one-liner."),
        ("h", "Data protection"),
        ("b", "All data resident in europe-west2 (London). No US-region replicas."),
        ("b", "Google-managed encryption keys by default; customer-managed keys (CMEK) available on request."),
        ("b", "Predictions are persisted to BigQuery with the same access controls as your existing analytics estate."),
        ("h", "Supply chain"),
        ("b", "Container images pinned by digest; dependency scanning runs on every PR; no third-party model weights are downloaded at runtime."),
    ], font_size=13)
    footer(s, prs, 10)


def slide_data_model(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Data and model lifecycle",
              eyebrow="From your ledger to a live prediction")
    body_box(s, prs, [
        ("h", "Ingestion"),
        ("b", "Real click events arrive via Pub/Sub or push-down query into BigQuery — schema and freshness are agreed in the data contract."),
        ("b", "Sales-ledger data is loaded via scheduled query or transfer service from the client source of truth."),
        ("h", "Training"),
        ("b", "Model is trained in a Vertex AI pipeline run from the same monorepo — fully reproducible from a commit."),
        ("b", "Each model version is registered in the Vertex Model Registry; we never deploy an unversioned artifact."),
        ("h", "Release"),
        ("b", "New versions deploy behind a traffic split — 10% canary, then ramp — with automatic rollback if breaker trip rates spike."),
        ("b", "Drift monitoring on inputs (PSI) and on outputs vs the reconciled ledger keeps the model honest in production."),
        ("mute", "Today's demo runs against a model trained on a synthetic dataset that mirrors the agreed schema. Retraining on real data is the first work item once the data contract is signed."),
    ], font_size=13)
    footer(s, prs, 11)


def slide_operability(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Operational readiness", eyebrow="Run-book ready, on day one")
    body_box(s, prs, [
        ("h", "Service-level objectives"),
        ("b", "Availability target 99.5% on /v1/score; latency SLO sized from the live load profile."),
        ("b", "Error-budget policy: breaches automatically open an incident channel."),
        ("h", "Observability"),
        ("b", "Cloud Logging, Cloud Trace, and Cloud Monitoring out of the box — one pane of glass for the on-call engineer."),
        ("b", "Four alert policies pre-wired: latency, error rate, breaker trips, anomaly state."),
        ("h", "Runbooks committed to the repository"),
        ("b", "Reset the breaker · Roll back a model version · Scale Vertex to zero for cost · Rotate a secret · Migrate the BigQuery schema."),
        ("h", "Rollback"),
        ("b", "Vertex traffic-split rollback to the previous model version is a single command; Cloud Run revisions are pinned and revertible."),
    ], font_size=13)
    footer(s, prs, 12)


def slide_roadmap(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Delivery roadmap", eyebrow="From here to production")

    # Phase cards
    phases = [
        ("Phase 1", "Staging hardened", "Complete",
         ["Real explain path live", "Sliding anomaly window",
          "IaC for IAM", "Load profile captured"], GREEN),
        ("Phase 2", "Real data", "In flight",
         ["Data contract sign-off", "Ingestion of client feeds",
          "Retrain on real data", "Canary 10% → 100%"], ACCENT),
        ("Phase 3", "Production", "Ready to start",
         ["Prod Terraform workspace", "Prod CD with approvals",
          "Right-sized Vertex", "Sign-off and handover"], TEAL),
    ]
    cw = Inches(4.2); ch = Inches(4.0); top = Inches(1.3)
    left0 = Inches(0.55); gap = Inches(0.25)
    for i, (phase, title, status, items, color) in enumerate(phases):
        x = left0 + i * (cw + gap)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, cw, ch)
        card.adjustments[0] = 0.05
        fill(card, WHITE)
        card.line.color.rgb = RULE
        card.line.width = Pt(0.75)
        # header stripe
        stripe = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, cw, Inches(0.55))
        fill(stripe, color)
        hb = s.shapes.add_textbox(x + Inches(0.2), top + Inches(0.07),
                                  cw - Inches(0.4), Inches(0.5))
        p = hb.text_frame.paragraphs[0]
        run(p, phase, size=11, bold=True, color=WHITE)
        p2 = hb.text_frame.add_paragraph()
        run(p2, title, size=15, bold=True, color=WHITE)
        # status pill
        sb = s.shapes.add_textbox(x + Inches(0.2), top + Inches(0.75),
                                  cw - Inches(0.4), Inches(0.3))
        p = sb.text_frame.paragraphs[0]
        run(p, status.upper(), size=10, bold=True, color=color)
        # items
        ib = s.shapes.add_textbox(x + Inches(0.25), top + Inches(1.15),
                                  cw - Inches(0.5), ch - Inches(1.3))
        tf = ib.text_frame; tf.word_wrap = True
        for j, it in enumerate(items):
            pp = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            pp.line_spacing = 1.25
            run(pp, "✓  " if status == "Complete" else "•  ",
                size=12, bold=True, color=color)
            run(pp, it, size=12, color=SLATE)

    note = s.shapes.add_textbox(Inches(0.55), Inches(5.45),
                                prs.slide_width - Inches(1.1), Inches(0.7))
    p = note.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run(p, "Indicative timeline: ~8 weeks from kickoff, gated on data access. "
        "Each phase ends in a working, demoable artefact.",
        size=11, italic=True, color=MUTED)
    footer(s, prs, 13)


def slide_commercials(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "What we need from you", eyebrow="Next steps to unlock value")
    body_box(s, prs, [
        ("h", "Three decisions"),
        ("b", "Sign off the data contract — schema, freshness, and PII handling for click and sales-ledger feeds."),
        ("b", "Nominate one data owner and one on-call engineer on your side for joint working sessions."),
        ("b", "Confirm production GCP project (or authorise a prod-isolated namespace in the existing one)."),
        ("h", "Two artefacts we will share this week"),
        ("b", "A short data-contract template ready for legal and engineering review."),
        ("b", "Read-only access to the live staging environment for your team to probe."),
        ("h", "What you get in eight weeks"),
        ("b", "A production service, on your data, with your on-call team in the cockpit and a signed handover."),
    ], font_size=14)
    footer(s, prs, 14)


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
    run(p, "Predictive RPC Estimator  ·  Live demo  ·  Q&A",
        size=18, color=LIGHT)

    foot = s.shapes.add_textbox(Inches(0.7), Inches(6.7), Inches(12), Inches(0.4))
    p = foot.text_frame.paragraphs[0]
    run(p, f"Live dashboard  ·  {DEMO_URL}", size=11, color=ACCENT)


def main():
    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_cover(prs)            # 1
    slide_exec_summary(prs)     # 2
    slide_problem(prs)          # 3
    slide_solution(prs)         # 4
    slide_deliverables(prs)     # 5
    slide_architecture(prs)     # 6
    slide_demo_script(prs)      # 7
    slide_performance(prs)      # 8
    slide_engineering(prs)      # 9
    slide_security(prs)         # 10
    slide_data_model(prs)       # 11
    slide_operability(prs)      # 12
    slide_roadmap(prs)          # 13
    slide_commercials(prs)      # 14
    slide_thanks(prs)           # 15

    prs.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
