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

    footer(s, prs, 5)


def slide_architecture(prs):
    """Engineering architecture, redesigned for visual discipline:
    three horizontal lanes, right-angle (elbow) arrows only,
    dedicated routing channels, no overlapping lines.
    """
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title_bar(s, prs, "End-to-end architecture",
              eyebrow="Predictive RPC Estimator")

    # Palette
    BLUE_SVC   = RGBColor(0x4E, 0x88, 0xE6)
    BLUE_DEEP  = RGBColor(0x1F, 0x4C, 0xA6)
    GREEN_VTX  = RGBColor(0x34, 0xA8, 0x53)
    TEAL_PIPE  = RGBColor(0x00, 0x97, 0xA7)
    PURPLE_BQ  = RGBColor(0x7E, 0x57, 0xC2)
    PUBSUB     = RGBColor(0xA0, 0x6C, 0xD6)
    GREY_BG    = RGBColor(0xF1, 0xF3, 0xF8)
    GREY_LINE  = RGBColor(0xC9, 0xCF, 0xDA)
    LANE_BG_A  = RGBColor(0xE8, 0xEF, 0xF7)
    LANE_BG_B  = RGBColor(0xF1, 0xEC, 0xF8)
    LANE_BG_C  = RGBColor(0xEC, 0xF3, 0xEE)
    ARROW      = RGBColor(0x46, 0x55, 0x6B)

    # ── GCP boundary ──────────────────────────────────────────────
    BX, BY = Inches(0.4), Inches(1.1)
    BW, BH = prs.slide_width - Inches(0.8), Inches(5.6)
    boundary = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, BX, BY, BW, BH)
    boundary.adjustments[0] = 0.015
    fill(boundary, GREY_BG)
    boundary.line.color.rgb = GREY_LINE
    boundary.line.width = Pt(1.0)

    cap = s.shapes.add_textbox(BX + Inches(0.18), BY + Inches(0.06),
                               Inches(8), Inches(0.3))
    pp = cap.text_frame.paragraphs[0]
    run(pp, "Google Cloud Platform", size=11, bold=True, color=NAVY)
    run(pp, "    europe-west2 (London)", size=10, color=MUTED, italic=True)

    # ── Lane geometry (3 lanes, equal height, generous gaps) ─────
    inner_x = BX + Inches(0.25)
    inner_w = BW - Inches(0.5)
    lane_top   = BY + Inches(0.5)
    lane_h     = Inches(1.45)
    lane_gap   = Inches(0.15)
    laneA_y = lane_top
    laneB_y = laneA_y + lane_h + lane_gap
    laneC_y = laneB_y + lane_h + lane_gap

    def lane_bg(y, color, label):
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, inner_x, y, inner_w, lane_h)
        fill(bg, color)
        bg.line.color.rgb = GREY_LINE; bg.line.width = Pt(0.5)
        lab = s.shapes.add_textbox(inner_x + Inches(0.1), y + Inches(0.05),
                                   Inches(3.0), Inches(0.25))
        p = lab.text_frame.paragraphs[0]
        run(p, label.upper(), size=8, bold=True, color=MUTED)

    lane_bg(laneA_y, LANE_BG_A, "Hot path · serving")
    lane_bg(laneB_y, LANE_BG_B, "Data plane · warehouse and training")
    lane_bg(laneC_y, LANE_BG_C, "Consumption · resilience and activation")

    # ── Helpers ──────────────────────────────────────────────────
    def comp(left, top, w, h, label, sublabel, color=BLUE_SVC, text=WHITE,
             label_size=11, sub_size=8):
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
        box.adjustments[0] = 0.10
        fill(box, color)
        box.line.fill.background()
        tf = box.text_frame
        tf.margin_left = Inches(0.08); tf.margin_right = Inches(0.08)
        tf.margin_top = Inches(0.05); tf.margin_bottom = Inches(0.05)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run(p, label, size=label_size, bold=True, color=text)
        if sublabel:
            p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
            run(p2, sublabel, size=sub_size, color=text)
        return box

    def hex_topic(left, top, w, h, name):
        box = s.shapes.add_shape(MSO_SHAPE.HEXAGON, left, top, w, h)
        fill(box, PUBSUB)
        box.line.fill.background()
        tf = box.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run(p, "Pub/Sub", size=9, bold=True, color=WHITE)
        # caption underneath
        cap = s.shapes.add_textbox(left - Inches(0.15), top + h + Inches(0.02),
                                   w + Inches(0.3), Inches(0.22))
        pc = cap.text_frame.paragraphs[0]; pc.alignment = PP_ALIGN.CENTER
        run(pc, name, size=8, color=SLATE)
        return box

    def line_segment(x1, y1, x2, y2, color=ARROW, weight=1.25, with_head=False):
        con = s.shapes.add_connector(1, x1, y1, x2, y2)
        con.line.color.rgb = color
        con.line.width = Pt(weight)
        if with_head:
            from pptx.oxml.ns import qn
            ln = con.line._get_or_add_ln()
            tail = ln.makeelement(qn('a:tailEnd'),
                                  {'type': 'triangle', 'w': 'med', 'h': 'med'})
            ln.append(tail)
        return con

    def arrow_h(x1, x2, y, color=ARROW, weight=1.25):
        """Horizontal arrow with head at (x2,y)."""
        line_segment(x1, y, x2, y, color=color, weight=weight, with_head=True)

    def arrow_v(x, y1, y2, color=ARROW, weight=1.25):
        line_segment(x, y1, x, y2, color=color, weight=weight, with_head=True)

    def elbow(x1, y1, x2, y2, via="h", color=ARROW, weight=1.25):
        """Right-angle two-segment connector with arrowhead on the second."""
        if via == "h":  # horizontal first, then vertical
            line_segment(x1, y1, x2, y1, color=color, weight=weight)
            line_segment(x2, y1, x2, y2, color=color, weight=weight, with_head=True)
        else:  # vertical first, then horizontal
            line_segment(x1, y1, x1, y2, color=color, weight=weight)
            line_segment(x1, y2, x2, y2, color=color, weight=weight, with_head=True)

    def text_at(left, top, w, h, text, size=8, color=MUTED, bold=False, italic=True,
                align=PP_ALIGN.CENTER):
        tb = s.shapes.add_textbox(left, top, w, h)
        tf = tb.text_frame; tf.word_wrap = True
        tf.margin_left = Inches(0.02); tf.margin_right = Inches(0.02)
        tf.margin_top = Inches(0); tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]; p.alignment = align
        run(p, text, size=size, color=color, bold=bold, italic=italic)
        return tb

    def actor(left, top, label):
        head = s.shapes.add_shape(MSO_SHAPE.OVAL, left + Inches(0.15), top,
                                  Inches(0.22), Inches(0.22))
        fill(head, SLATE)
        body = s.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE,
                                  left, top + Inches(0.20),
                                  Inches(0.52), Inches(0.42))
        fill(body, SLATE)
        cap = s.shapes.add_textbox(left - Inches(0.2), top + Inches(0.65),
                                   Inches(0.92), Inches(0.3))
        p = cap.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run(p, label, size=9, bold=True, color=SLATE)

    # ── LANE A — Hot path ────────────────────────────────────────
    # Components on a single horizontal line, generous spacing.
    a_box_top = laneA_y + Inches(0.45)
    a_box_h   = Inches(0.85)
    # Define centerline for paired arrows
    A_CENTER = a_box_top + a_box_h / 2

    # Scoring API
    scoring_x = Inches(1.7); scoring_w = Inches(2.8)
    comp(scoring_x, a_box_top, scoring_w, a_box_h,
         "Scoring API", "Rust 1.89  ·  Cloud Run", color=BLUE_SVC)

    # Vertex AI
    vertex_x = Inches(5.4); vertex_w = Inches(2.6)
    comp(vertex_x, a_box_top, vertex_w, a_box_h,
         "Vertex AI Endpoint", "XGBoost regressor", color=GREEN_VTX)

    # Dashboard UI
    dash_x = Inches(9.9); dash_w = Inches(2.6)
    comp(dash_x, a_box_top, dash_w, a_box_h,
         "Dashboard UI", "TypeScript · React · nginx · Cloud Run",
         color=BLUE_SVC)

    # Actors
    actor(Inches(0.7), laneA_y + Inches(0.5), "Client")
    actor(Inches(12.65) + Inches(0.0) - Inches(0.6), laneA_y + Inches(0.5), "Executive")

    # Hot-path arrows (strictly horizontal, paired req/resp)
    arrow_h(Inches(1.25), scoring_x, A_CENTER - Inches(0.04))
    text_at(Inches(1.25), A_CENTER - Inches(0.32), Inches(0.55), Inches(0.2),
            "HTTPS", size=7)
    # Scoring → Vertex (predict)
    arrow_h(scoring_x + scoring_w, vertex_x, A_CENTER - Inches(0.15))
    text_at(scoring_x + scoring_w, A_CENTER - Inches(0.36),
            vertex_x - (scoring_x + scoring_w), Inches(0.2),
            "predict", size=7)
    # Vertex → Scoring (predicted_rpc)
    arrow_h(vertex_x, scoring_x + scoring_w, A_CENTER + Inches(0.15))
    text_at(scoring_x + scoring_w, A_CENTER + Inches(0.15),
            vertex_x - (scoring_x + scoring_w), Inches(0.2),
            "predicted_rpc", size=7)
    # Executive → Dashboard
    arrow_h(Inches(12.55) - Inches(0.0), dash_x + dash_w, A_CENTER)

    # Guardrails callout under Scoring (still inside Lane A)
    guard_y = a_box_top + a_box_h - Inches(0.05)
    # nothing more needed — guardrails listed in legend/footnote

    # ── LANE B — Data plane ──────────────────────────────────────
    b_box_top = laneB_y + Inches(0.45)
    b_box_h   = Inches(0.85)
    B_CENTER  = b_box_top + b_box_h / 2

    # Pub/Sub: predictions  (directly below Scoring API)
    ps_pred_w = Inches(1.3); ps_pred_h = Inches(0.55)
    ps_pred_x = scoring_x + (scoring_w - ps_pred_w) / 2
    ps_pred_y = b_box_top + Inches(0.05)
    hex_topic(ps_pred_x, ps_pred_y, ps_pred_w, ps_pred_h, "rpc-predictions-staging")

    # BigQuery warehouse
    bq_x = Inches(5.4); bq_w = Inches(2.6); bq_h = Inches(1.05)
    bq_y = b_box_top - Inches(0.08)
    bqshape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bq_x, bq_y, bq_w, bq_h)
    bqshape.adjustments[0] = 0.08
    fill(bqshape, PURPLE_BQ); bqshape.line.fill.background()
    tf = bqshape.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.08); tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.06)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run(p, "BigQuery", size=11, bold=True, color=WHITE)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    run(p2, "Data warehouse", size=8, color=WHITE)
    p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.CENTER
    p3.space_before = Pt(3)
    run(p3, "rpc_predictions  ·  sales_ledger", size=7, italic=True, color=WHITE)
    p4 = tf.add_paragraph(); p4.alignment = PP_ALIGN.CENTER
    run(p4, "predictions_vs_revenue", size=7, italic=True, color=WHITE)

    # ML Ops Pipeline
    ml_x = Inches(9.0); ml_w = Inches(2.4)
    comp(ml_x, b_box_top, ml_w, b_box_h,
         "ML Ops Pipeline", "Python 3.12  ·  Vertex AI Pipelines",
         color=TEAL_PIPE)

    # Cloud Storage (model artifacts)
    cs_x = Inches(11.7); cs_w = Inches(0.7); cs_h = Inches(0.85)
    can = s.shapes.add_shape(MSO_SHAPE.CAN, cs_x, b_box_top, cs_w, cs_h)
    fill(can, MUTED); can.line.fill.background()
    cs_cap = s.shapes.add_textbox(cs_x - Inches(0.15), b_box_top + cs_h - Inches(0.02),
                                  cs_w + Inches(0.3), Inches(0.25))
    pcs = cs_cap.text_frame.paragraphs[0]; pcs.alignment = PP_ALIGN.CENTER
    run(pcs, "Cloud Storage", size=7, bold=True, color=SLATE)

    # Lane B arrows (horizontal only)
    # Pub/Sub predictions → BigQuery
    arrow_h(ps_pred_x + ps_pred_w, bq_x,
            ps_pred_y + ps_pred_h / 2)
    text_at(ps_pred_x + ps_pred_w, ps_pred_y - Inches(0.14),
            bq_x - (ps_pred_x + ps_pred_w), Inches(0.18),
            "BigQuery sub", size=7)
    # BigQuery → ML Pipeline (training data)
    arrow_h(bq_x + bq_w, ml_x, B_CENTER)
    text_at(bq_x + bq_w, B_CENTER - Inches(0.22),
            ml_x - (bq_x + bq_w), Inches(0.2),
            "training data", size=7)
    # ML Pipeline → Cloud Storage (artifacts)
    arrow_h(ml_x + ml_w, cs_x, B_CENTER)
    text_at(ml_x + ml_w, B_CENTER - Inches(0.22),
            cs_x - (ml_x + ml_w), Inches(0.18),
            "artifacts", size=7)

    # ── Inter-lane: Scoring → Pub/Sub predictions (straight down) ──
    arrow_v(ps_pred_x + ps_pred_w / 2,
            a_box_top + a_box_h,
            ps_pred_y, weight=1.25)
    text_at(ps_pred_x + ps_pred_w / 2 - Inches(0.55),
            a_box_top + a_box_h + Inches(0.02),
            Inches(1.1), Inches(0.18),
            "emit prediction", size=7)

    # ── Inter-lane: ML Pipeline → Vertex (deploy, dashed) ────────
    # Use a clean elbow that runs in the channel BETWEEN lanes, not through any box.
    channel_y = laneA_y + lane_h + lane_gap / 2  # mid-channel between A and B
    # Start from ML Pipeline top, go up to channel, across left to Vertex bottom-center.
    ml_top_center_x = ml_x + ml_w / 2
    vertex_bottom_x = vertex_x + vertex_w / 2
    # Vertical from ML Pipeline top to channel
    line_segment(ml_top_center_x, b_box_top, ml_top_center_x, channel_y,
                 color=GREEN_VTX, weight=1.0)
    # Horizontal across channel to above Vertex
    line_segment(ml_top_center_x, channel_y, vertex_bottom_x, channel_y,
                 color=GREEN_VTX, weight=1.0)
    # Vertical down into Vertex
    line_segment(vertex_bottom_x, channel_y, vertex_bottom_x, a_box_top + a_box_h,
                 color=GREEN_VTX, weight=1.0, with_head=True)
    text_at(ml_top_center_x - Inches(1.5), channel_y - Inches(0.18),
            Inches(1.4), Inches(0.18),
            "deploy / retrain", size=7, color=GREEN_VTX)

    # ── LANE C — Consumption ─────────────────────────────────────
    c_box_top = laneC_y + Inches(0.45)
    c_box_h   = Inches(0.85)
    C_CENTER  = c_box_top + c_box_h / 2

    # Breaker Automation (below Scoring, lane C)
    br_x = scoring_x; br_w = Inches(2.2)
    comp(br_x, c_box_top, br_w, c_box_h,
         "Breaker Automation", "Python  ·  flips kill-switch", color=BLUE_SVC)

    # Secret Manager (between breaker and bq area)
    sm_x = br_x + br_w + Inches(0.2); sm_w = Inches(1.5); sm_h = Inches(0.55)
    sm_y = c_box_top + Inches(0.15)
    sm = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, sm_x, sm_y, sm_w, sm_h)
    sm.adjustments[0] = 0.2
    fill(sm, WHITE); sm.line.color.rgb = GREY_LINE; sm.line.width = Pt(0.75)
    tf = sm.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run(p, "Secret Manager", size=9, bold=True, color=NAVY)

    # Reconciliation Service (directly below BigQuery)
    rc_x = bq_x; rc_w = bq_w
    comp(rc_x, c_box_top, rc_w, c_box_h,
         "Reconciliation Service", "Python FastAPI  ·  Cloud Run",
         color=BLUE_SVC)

    # Activation Service (right side)
    av_x = Inches(9.0); av_w = Inches(2.4)
    comp(av_x, c_box_top, av_w, c_box_h,
         "Activation Service", "Python 3.12  ·  Cloud Run",
         color=BLUE_SVC)

    # Sinks
    sinks_x = av_x + av_w + Inches(0.15)
    for i, sink in enumerate(["SA360", "SSGTM", "OCI"]):
        lab = s.shapes.add_textbox(sinks_x, c_box_top + Inches(0.05) + Inches(i * 0.26),
                                   Inches(1.0), Inches(0.24))
        p = lab.text_frame.paragraphs[0]
        run(p, "→  " + sink, size=9, bold=True, color=SLATE)

    # Lane C arrows (horizontal within lane)
    # Breaker → Secret Manager
    arrow_h(br_x + br_w, sm_x, sm_y + sm_h / 2)
    # Activation → sinks (single arrow into sink column)
    arrow_h(av_x + av_w, sinks_x - Inches(0.05), C_CENTER)

    # ── Inter-lane: Secret Manager → Scoring (up channel) ───────
    sm_cx = sm_x + sm_w / 2
    # vertical up through lane B channel — but must avoid traversing BQ.
    # SM is at x ≈ 4.7. BQ is x=5.4..8.0. So a straight vertical at 4.7 will
    # pass through Lane B background but NOT through BQ (which starts at 5.4).
    # That clears the requirement: no arrow crosses a component box.
    line_segment(sm_cx, sm_y, sm_cx, a_box_top + a_box_h,
                 color=ARROW, weight=1.0, with_head=True)
    text_at(sm_cx + Inches(0.05), (sm_y + a_box_top + a_box_h) / 2 - Inches(0.1),
            Inches(1.6), Inches(0.18),
            "kill-switch flag", size=7, italic=True, color=MUTED, align=PP_ALIGN.LEFT)

    # ── Inter-lane: BigQuery → Reconciliation (straight down) ───
    bq_bot_cx = bq_x + bq_w / 2
    line_segment(bq_bot_cx, bq_y + bq_h, bq_bot_cx, c_box_top,
                 color=ARROW, weight=1.25, with_head=True)
    text_at(bq_bot_cx - Inches(1.2), (bq_y + bq_h + c_box_top) / 2 - Inches(0.1),
            Inches(1.1), Inches(0.18),
            "predictions_vs_revenue", size=7)

    # ── Inter-lane: Reconciliation → Dashboard (straight up) ────
    rec_top_cx = rc_x + rc_w - Inches(0.4)
    # Need to avoid BigQuery. Route along right edge of Reconciliation column.
    # Go up via the gap channel between BigQuery and Dashboard (x ~ 8.4)
    channel_x = Inches(8.4)
    # First: out the right of Reconciliation
    line_segment(rc_x + rc_w, C_CENTER, channel_x, C_CENTER,
                 color=ARROW, weight=1.0)
    # Up through lane gaps to lane A
    line_segment(channel_x, C_CENTER, channel_x, A_CENTER,
                 color=ARROW, weight=1.0)
    # Right into Dashboard
    line_segment(channel_x, A_CENTER, dash_x, A_CENTER,
                 color=ARROW, weight=1.0, with_head=True)
    text_at(channel_x + Inches(0.05), A_CENTER - Inches(0.22),
            Inches(1.1), Inches(0.18),
            "HTTPS /api", size=7, italic=True, color=MUTED, align=PP_ALIGN.LEFT)

    # ── Inter-lane: BigQuery → Activation (down-right) ──────────
    # Activation reads predictions from BQ to push to sinks. Route via channel_x.
    line_segment(bq_x + bq_w, bq_y + bq_h - Inches(0.25),
                 av_x + Inches(0.4), bq_y + bq_h - Inches(0.25),
                 color=ARROW, weight=1.0)
    line_segment(av_x + Inches(0.4), bq_y + bq_h - Inches(0.25),
                 av_x + Inches(0.4), c_box_top,
                 color=ARROW, weight=1.0, with_head=True)
    text_at(av_x - Inches(0.4), bq_y + bq_h - Inches(0.45),
            Inches(1.6), Inches(0.18),
            "predictions", size=7)

    # ── Footnote: guardrails & CI/CD (text only, no diagram clutter) ─
    foot = s.shapes.add_textbox(BX + Inches(0.25), BY + BH - Inches(0.55),
                                BW - Inches(0.5), Inches(0.5))
    tf = foot.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]
    run(p, "Scoring API guardrails:  ", size=9, bold=True, color=BLUE_DEEP)
    run(p, "prediction bounds  ·  negative clamp  ·  model & BigQuery timeouts  ·  anomaly window  ·  circuit-breaker  ·  kill-switch.", size=9, color=SLATE)
    p2 = tf.add_paragraph()
    run(p2, "Delivery:  ", size=9, bold=True, color=BLUE_DEEP)
    run(p2, "GitHub  →  Workload Identity Federation  →  Cloud Build  →  Artifact Registry  →  Cloud Run, gated on test, coverage and supply-chain scans.", size=9, color=SLATE)

    footer(s, prs, 6)


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