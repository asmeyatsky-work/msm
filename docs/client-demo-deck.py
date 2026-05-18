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
TOTAL_PAGES = 16


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
    run(p, "PREDICTIVE REVENUE INTELLIGENCE — CREDIT CARDS MVP",
        size=12, bold=True, color=ACCENT)

    title = s.shapes.add_textbox(Inches(0.7), Inches(2.1), Inches(9), Inches(1.4))
    tf = title.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    run(p, "Predictive RPC Estimator", size=44, bold=True, color=WHITE)
    p2 = tf.add_paragraph()
    run(p2, "Real-time revenue-per-click forecasting for Credit Cards",
        size=20, color=LIGHT)

    sub = s.shapes.add_textbox(Inches(0.7), Inches(4.8), Inches(9), Inches(2))
    tf = sub.text_frame; tf.word_wrap = True
    for label, val in [
        ("Solution demo", "Live staging environment"),
        ("Audience", "Credit Cards leadership + technical stakeholders"),
        ("Date", "2026-05-18"),
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
        ("h", "A production-grade revenue forecasting service, Credit-Cards-shaped, on staging."),
        ("p", "End-to-end machine-learning service predicting revenue-per-click in real time — with the Credit Cards feature schema, the 90-day reconciliation window, the safety net, and four demo-grade visualisations purpose-built for this conversation."),
        ("h", "Four things to take away today"),
        ("b", "A live model you can drive — describe a Credit Cards click in business language, press Predict, see the predicted bid, the value-based vs flat-tCPA comparison, and the explanation, all under a second."),
        ("b", "The behavioural-signal layer (Phoebe / GA4) is wired into the schema and the dashboard, day one — see the user-journey animation drive the bid in real time."),
        ("b", "Three failure modes commonly seen in prior value-based-bidding attempts are addressed in the platform, with the file references to prove it."),
        ("b", "A clear path to your real data: 50% → 80% coverage trajectory fits the model lifecycle. End-August cutover is the target; the schema, dashboards, alerts, and CD path are already running on staging."),
    ], font_size=14)
    footer(s, prs, 2)


def slide_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "The opportunity — Credit Cards, now",
              eyebrow="Why this vertical, why this quarter")
    body_box(s, prs, [
        ("h", "Credit Cards PPC is under-using the sales data you already have."),
        ("p", "Flat target-CPA bidding treats every Credit Cards click as the same tin of beans. The whales that actually pay back the customer-acquisition cost are over-paid for in one campaign and under-bid in another — and you only find out 90 days later when the ledger reconciles."),
        ("h", "Why act on Credit Cards before the other verticals"),
        ("b", "Near-term commercial pressure on the channel — first vertical to pay back the platform investment."),
        ("b", "Sales coverage is rising — 50% today to ~80% by end of June. The model lifecycle re-trains as coverage climbs."),
        ("b", "Lower risk than Car Insurance: bid-optimisation only, no customer-decisioning surface — keeps the FCA boundary clean."),
        ("h", "What a predictive RPC unlocks"),
        ("b", "Bid the click that's likely to convert — not the click that already did."),
        ("b", "Reallocate spend within the hour, not the week, with the value-based bid replacing the flat tCPA target."),
        ("b", "Detect campaign degradation before it shows up in revenue — per-segment drift alerts, week-over-week."),
        ("b", "Explain every prediction in plain English — auditability for finance and compliance."),
    ], font_size=13)
    footer(s, prs, 3)


def slide_solution(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Solution overview", eyebrow="What we have built")
    body_box(s, prs, [
        ("h", "A managed prediction service on Google Cloud, sized for Credit Cards."),
        ("b", "Executive dashboard — KPIs in pounds, 90-day default window, product-type filter, coverage-audit panel, active-model-versions panel."),
        ("b", "Interactive prediction — Credit-Cards-shaped form (product type, card product, query intent, affinity, prior-applicant, income band, two RPC rollups, plus four Phoebe behavioural signals)."),
        ("b", "Hero before/after — same click, side-by-side: flat-tCPA target vs value-based bid vs difference, with a session counter that runs total over time."),
        ("b", "Phoebe journey — animated 6-step replay of a single user's behavioural signal building up and the predicted bid following it."),
        ("b", "Explainable AI — every prediction returns per-feature attributions in plain English; 'Likely-to-apply score', 'Recent 14-day earnings', 'Time engaged'."),
        ("b", "REST API — the same predictions available programmatically for SA360, SSGTM, OCI downstream activation."),
        ("b", "Safety net — anomaly detection, automatic circuit-breaker, negative-prediction guards, per-call timeouts, kill-switch flag."),
        ("b", "Per-segment drift + coverage-drop alerts — Cloud Monitoring policies fire on the dimensions that matter for CC (product_type × device × geo)."),
        ("b", "One-command deploys — tag push runs CI then CD; tested rollback to the prior model version is a single Vertex traffic-split."),
        ("mute", "All components run in Google Cloud (europe-west2, London) on managed services — Cloud Run, Vertex AI, BigQuery, Pub/Sub, Cloud Monitoring — no infrastructure for the client team to operate."),
    ], font_size=12)
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
        ("scoring-api  /v1/score, /v1/explain  (Rust)",
         "Bidder integration: SA360 / SSGTM / OCI",
         "API only — invoked live by the dashboard",
         "api"),
        ("reconciliation  /reconciliation, /coverage",
         "Powers the dashboard",
         "API only — invisible to client",
         "api"),
        ("activation  (Python)",
         "SA360 / SSGTM / OCI push",
         "Backend, no UI",
         "backend"),
        ("breaker-automation, ml-pipeline, bounds-calibration",
         "Internal / scheduled training and recovery",
         "Backend",
         "backend"),
        ("Dataform: phoebe_features, coverage_audit, drift / coverage breach views",
         "Analyst + monitoring layer",
         "BigQuery direct or Looker Studio",
         "optional"),
        ("ops/breach_emitter.py",
         "Daily Cloud-Scheduler driven breach → alert emitter",
         "Backend",
         "backend"),
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

    footer(s, prs, 5)


def slide_architecture(prs):
    """Embeds docs/architecture.png as the full architecture slide.
    Save the chosen render to that path. If the file is missing, the slide
    shows a placeholder so the deck still builds.
    """
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "End-to-end architecture",
              eyebrow="Predictive RPC Estimator")

    img_path = Path(__file__).parent / "architecture.png"
    if img_path.exists():
        # Fit image into the body area, preserving aspect ratio.
        canvas_left   = Inches(0.4)
        canvas_top    = Inches(1.15)
        canvas_width  = prs.slide_width  - Inches(0.8)
        canvas_height = prs.slide_height - Inches(1.5) - Inches(0.35)  # leave footer
        from PIL import Image  # type: ignore
        try:
            with Image.open(img_path) as im:
                iw, ih = im.size
            aspect = iw / ih
            if canvas_width / canvas_height > aspect:
                # constrained by height
                h = canvas_height
                w = int(h * aspect)
            else:
                w = canvas_width
                h = int(w / aspect)
            left = canvas_left + (canvas_width - w) // 2
            top  = canvas_top  + (canvas_height - h) // 2
            s.shapes.add_picture(str(img_path), left, top, width=w, height=h)

            # Typo overlay: 'Calbration' → 'Calibration'.
            # Pixel rect in the 1408×768 source image covering the
            # entire "Bounds Calbration Job" label line.
            def px_to_emu(px, axis_size_emu, axis_size_px):
                return int(px / axis_size_px * axis_size_emu)
            OV_X, OV_Y, OV_W, OV_H = 180, 343, 175, 26
            ov_left = left + px_to_emu(OV_X, w, iw)
            ov_top  = top  + px_to_emu(OV_Y, h, ih)
            ov_w    = px_to_emu(OV_W, w, iw)
            ov_h    = px_to_emu(OV_H, h, ih)
            # Blue cover matching the source box fill (sampled from the image).
            BOX_BLUE = RGBColor(0x4E, 0x82, 0xD5)
            cover = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                       ov_left, ov_top, ov_w, ov_h)
            fill(cover, BOX_BLUE)
            tf = cover.text_frame
            tf.margin_left = Pt(0); tf.margin_right = Pt(0)
            tf.margin_top = Pt(0); tf.margin_bottom = Pt(0)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = "Bounds Calibration Job"
            r.font.size = Pt(10); r.font.bold = True
            r.font.color.rgb = WHITE; r.font.name = "Calibri"
        except Exception:
            s.shapes.add_picture(str(img_path), canvas_left, canvas_top,
                                 width=canvas_width)
    else:
        # Placeholder
        box = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(2), Inches(2.8), Inches(9.3), Inches(2),
        )
        box.adjustments[0] = 0.05
        fill(box, LIGHT)
        box.line.color.rgb = RULE; box.line.width = Pt(0.75)
        tf = box.text_frame; tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.4); tf.margin_right = Inches(0.4)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run(p, "Architecture diagram", size=18, bold=True, color=NAVY)
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        run(p2, "Save the chosen render as  docs/architecture.png  and regenerate the deck.",
            size=12, color=MUTED, italic=True)

    footer(s, prs, 6)


def slide_demo_script(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Live demo — what you will see",
              eyebrow="Seven minutes, one URL")
    body_box(s, prs, [
        ("h", "1.  KPIs in pounds, 90-day default — and a product-type filter."),
        ("p", "We open the dashboard. Five KPIs — clicks scored, expected vs realised earning, typical error, and conversion coverage — explain accuracy in business language. The window defaults to 90 days for Credit Cards. The product-type filter re-segments the chart in one click."),
        ("h", "2.  Where we have full visibility — coverage panel."),
        ("p", "A bar chart shows coverage % per product-type slice. Red bars are slices below 60% — the slices where we'd ask for ingestion backfill before retraining. This is how we answer the 50% question, slice by slice, not as an aggregate."),
        ("h", "3.  Hero before/after — flat tCPA vs value-based bid, on the same click."),
        ("p", "Three side-by-side cards: Old-world flat target-CPA, New-world value-based bid (70% of predicted RPC), and the difference — over-paid prevented or under-bid recovered. A session counter accumulates the total across every prediction the audience fires."),
        ("h", "4.  You drive the model — yourself."),
        ("p", "Form fields in Credit-Cards language: product type, card product, query intent (compare/shop/apply/research), 'how likely to apply', 'used a calculator', 'guides read', 'cards compared', 'time engaged'. Press Predict — the pipeline-trace lights up in real time: validate → guardrails → Vertex AI → BigQuery → SHAP."),
        ("h", "5.  The Phoebe journey — bouncer with a crystal ball."),
        ("p", "Press Play. A single user moves through six steps — search → page view → calculator → guides → compare-5 → click. The predicted bid ticks up under each step card as their behavioural signal builds. A lift pill shows the £ gap from first to last step."),
        ("h", "6.  Why the model said that."),
        ("p", "Horizontal-bar attribution chart on every prediction. Names are in business English ('Likely-to-apply score', 'Recent 14-day earnings', 'Time engaged'). Auditable for finance and compliance — ADR 0004 forbids these signals reaching customer terms."),
        ("h", "7.  The platform context — what we've designed against; what's next."),
        ("p", "Three failure modes named at the bottom of the page — pricing leakage, uncontrolled bidding, invisible decay — each mapped to where the platform pushes back. And a five-vertical roadmap: Credit Cards live, Loans / Home / Life / Mortgages dated."),
        ("mute", f"Live dashboard  ·  {DEMO_URL}"),
    ], font_size=11)
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


def slide_tech_choices(prs):
    """The slide that pre-empts 'are you sure you didn't just pick the
    default' questions from a CTO room. Two-column rationale grid."""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Why these technology choices",
              eyebrow="What we evaluated, and what we chose")

    left_col = [
        ("h", "Hot path — Rust on Cloud Run"),
        ("b", "Latency budget: /v1/score p99 ≤ 2.5 s end-to-end; Vertex AI predict round-trip dominates ~700 ms. Rust gives us the rest of the budget for safety-net composition (bounds → fallback, circuit breaker, anomaly window) with zero GC jitter."),
        ("b", "Considered Go and Python; both leave less headroom and complicate the breaker's idempotency guarantees."),
        ("h", "Model — XGBoost on Vertex AI"),
        ("b", "Feature space is tabular and ~11 columns wide. GBDT is the empirically dominant family for tabular regression at this scale."),
        ("b", "Vertex's prebuilt xgboost-cpu container ships native explanationSpec (Sampled-Shapley) — /v1/explain comes free; deep models need a separate KernelSHAP that's slower, noisier, harder to audit under ADR 0004."),
        ("b", "Deterministic predict call composes cleanly with the circuit breaker; transformers' stateful decoding would not."),
        ("h", "Frontend — TypeScript + React + Vite"),
        ("b", "Single demo URL; realtime interactivity (live prediction, animated Phoebe journey). Zod validates the JSON at the boundary."),
        ("b", "No server-side rendering — keeps the dashboard a static-asset deploy behind a single Cloud Run service."),
    ]
    right_col = [
        ("h", "Cross-service contracts — Protobuf"),
        ("b", "Wire stability across Rust ↔ Python; codegen per language; cross-language parity test in CI guards drift."),
        ("b", "Considered JSON Schema — adequate, but loses the on-wire byte-stability we rely on for the audit trail."),
        ("h", "Data layer — Dataform on BigQuery"),
        ("b", "Same SQL primitives as dbt; one less tool the client team has to install and learn."),
        ("b", "Type-safe ref()s give us the dependency graph automatically: coverage_audit, residuals_by_segment, drift_breaches_weekly all light up in the right order."),
        ("h", "Identity — Workload Identity Federation"),
        ("b", "GitHub OIDC federates into GCP. No long-lived service-account keys to rotate, leak, or audit."),
        ("b", "Per-service service accounts; every IAM grant is in Terraform — reviewable in git, not in the console."),
        ("h", "Runtime — Cloud Run"),
        ("b", "Request-driven autoscaling; min=1 keeps the demo warm at ~£3-5/day; max ramps under load tests without paging us."),
        ("b", "Considered GKE — overkill for a service that's CPU-bound and stateless; we'd pay for cluster overhead we don't use."),
    ]
    body_box(s, prs, left_col,
             top=Inches(1.2), left=Inches(0.5),
             width=Inches(6.2), font_size=10, line_spacing=1.15)
    body_box(s, prs, right_col,
             top=Inches(1.2), left=Inches(6.85),
             width=Inches(6.2), font_size=10, line_spacing=1.15)
    footer(s, prs, 10)


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
        ("h", "Compliance boundary"),
        ("b", "ADR 0004: bid-optimisation only. No customer identifiers ingested; no model output reaches any system that affects customer terms or eligibility."),
        ("b", "ADR 0005 (in flight): GA4 / Phoebe PII boundary — hashed user_pseudo_id only; raw user_id and PII event params stripped at the staging view."),
        ("h", "Supply chain"),
        ("b", "Container images pinned by digest; dependency scanning runs on every PR; no third-party model weights are downloaded at runtime."),
    ], font_size=12)
    footer(s, prs, 11)


def slide_data_model(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Data and model lifecycle",
              eyebrow="From your ledger to a live prediction")
    body_box(s, prs, [
        ("h", "Three feeds, one model"),
        ("b", "Click stream (CM360) — Credit Cards schema: product_type, card_product_id, query_intent (CC enum), affinity_score, prior_applicant, income_band_bucket, rpc_14d/60d, landing_path, visits_prev_30d."),
        ("b", "Sales ledger — multi-stage events (application_started → submitted → approved → activated → first_spend → chargeback) with revenue, margin_rate (Soteria-ready), card_product_id, currency."),
        ("b", "GA4 / Phoebe — behavioural rollup (calculator_used, guides_read, cards_compared, session_engagement_s), per cookie, nightly. Joined at training; looked up at serving."),
        ("h", "Label and reconciliation window"),
        ("b", "Sum-of-rewards over a 90-day window (ADR 0003 — fits the CC consideration tail). Profit-ready: realised label is SUM(revenue × COALESCE(margin_rate, 1.0)); commission table swaps in as a data-only change."),
        ("h", "Training and release"),
        ("b", "Vertex AI Pipelines run from the same monorepo — reproducible from a commit. Every version registered in Vertex Model Registry."),
        ("b", "Canary path: 10% traffic split → 50% over 48h → 100%. Active-versions panel on the dashboard shows the share and rolling MAE side-by-side."),
        ("b", "Drift on inputs (PSI per numeric feature), outputs (residuals_daily), per-segment (product × device × geo), and coverage (slice drop W-o-W)."),
        ("mute", "Today's demo runs against a model trained on a synthetic dataset that mirrors the agreed schema. Retraining on real Credit Cards data is the first work item once OQ-11 (GA4 access) and the data contract are signed."),
    ], font_size=12)
    footer(s, prs, 12)


def slide_operability(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Operational readiness", eyebrow="Run-book ready, on day one")
    body_box(s, prs, [
        ("h", "Service-level objectives"),
        ("b", "Availability target 99.5% on /v1/score; latency SLO sized from the live load profile (p95 ~920 ms vs 1500 ms threshold)."),
        ("b", "Error-budget policy: breaches automatically open an incident channel (notification channel pending OQ-2)."),
        ("h", "Observability"),
        ("b", "Cloud Logging, Cloud Trace, and Cloud Monitoring out of the box — one pane of glass for the on-call engineer."),
        ("b", "Six alert policies pre-wired: latency p95, error rate, breaker trips, anomaly state, per-segment MAE drift > 25% W-o-W, per-slice coverage drop > 10pp W-o-W."),
        ("h", "Runbooks committed to the repository"),
        ("b", "Reset the breaker · Roll back a model version · Scale Vertex to zero for cost · Rotate a secret · Migrate the BigQuery schema · Coverage audit (random-vs-systematic decision)."),
        ("h", "Rollback"),
        ("b", "Vertex traffic-split rollback to the previous model version is a single command; Cloud Run revisions are pinned and revertible."),
    ], font_size=12)
    footer(s, prs, 13)


def slide_roadmap(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "Delivery roadmap", eyebrow="From here to production")

    # Phase cards
    phases = [
        ("Phase 1", "Platform & schema", "Complete",
         ["Credit Cards schema end-to-end",
          "Phoebe behavioural features wired",
          "Demo dashboard live",
          "Drift + coverage alerting in place"], GREEN),
        ("Phase 2", "Real data (50% → 80%)", "Pending client",
         ["GA4 access (OQ-11) granted",
          "Click + ledger sample lands",
          "v1 trained on 50% coverage",
          "Canary 10% → 100% on client env"], ACCENT),
        ("Phase 3", "Cutover & handover", "End-August 2026",
         ["v2 retrained on 80% coverage",
          "Rollback rehearsed in low traffic",
          "Compliance sign-off on ADRs 0004/0005",
          "Handover to client on-call"], TEAL),
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
    run(p, "Timeline measured from data-sample arrival, not kickoff. "
        "Phase 1 is on staging today; Phase 2 starts the day GA4 access + a sample data export land.",
        size=11, italic=True, color=MUTED)
    footer(s, prs, 14)


def slide_commercials(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "What we need from you", eyebrow="Next steps to unlock value")
    body_box(s, prs, [
        ("h", "Five decisions, in priority order"),
        ("b", "GA4 access (OQ-11) — read on the Credit Cards analytics_<property> dataset. This is the critical path; everything downstream slips a week per week this slides."),
        ("b", "Confirm GA4 event taxonomy (OQ-12) — which event_name values map to 'calculator used', 'guide read', 'card compare'. Best-current-guess in our staging schema; one working session to validate."),
        ("b", "Click → cookie join key (OQ-13) — server-side CM360 + GA4 merge, first-party-cookie pass-through, or no-join. Decides whether Phoebe lifts the live model."),
        ("b", "GCP project (OQ-1) — client's own or a namespaced env in our msm-rpc project. We can move either way; the deploy-client-cc CD job is already wired and gated on the decision."),
        ("b", "Compliance contact + sign-off on ADRs 0004 (FCA boundary) and 0005 (GA4 PII boundary). Two named contacts: one data owner + one engineering lead."),
        ("h", "What you also get"),
        ("b", "The Car Insurance failure summary from Ryan refines our 'designed against' tile from speculation to confirmed mitigations."),
        ("b", "Read-only access to the live staging environment for your team to probe."),
        ("h", "What you get at the end"),
        ("b", "A production service, on your data, with your on-call team in the cockpit and a signed handover by end-August."),
    ], font_size=12)
    footer(s, prs, 15)


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
    slide_tech_choices(prs)     # 10  — new, tech-audience rationale
    slide_security(prs)         # 11
    slide_data_model(prs)       # 12
    slide_operability(prs)      # 13
    slide_roadmap(prs)          # 14
    slide_commercials(prs)      # 15
    slide_thanks(prs)           # 16

    prs.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()