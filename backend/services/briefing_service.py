"""
Doctor briefing PDF generator.

Takes a patient profile + their top trial matches and produces a 1–2 page PDF
the patient can hand to their oncologist. Frames the whole product around the
real decision-maker: doctors enroll patients in trials, not the other way
around.

Uses reportlab so the PDF is generated server-side with proper typography.
"""

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.patient import PatientProfile
from models.trial import MatchResponse, RankedTrial


BRAND = colors.HexColor("#1f6feb")
INK = colors.HexColor("#14202e")
INK_SOFT = colors.HexColor("#4a5a6a")
INK_FAINT = colors.HexColor("#7d8b99")
TINT = colors.HexColor("#eaf1fe")
GREEN = colors.HexColor("#1f9d57")
AMBER = colors.HexColor("#b8770a")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "title", parent=base["Title"], textColor=INK, fontSize=18, leading=22, spaceAfter=4
    )
    eyebrow = ParagraphStyle(
        "eyebrow",
        parent=base["Normal"],
        textColor=BRAND,
        fontSize=8,
        leading=10,
        spaceAfter=2,
        fontName="Helvetica-Bold",
    )
    h2 = ParagraphStyle(
        "h2", parent=base["Heading2"], textColor=INK, fontSize=12, leading=16, spaceAfter=4
    )
    h3 = ParagraphStyle(
        "h3", parent=base["Heading3"], textColor=INK, fontSize=11, leading=14, spaceAfter=2
    )
    body = ParagraphStyle(
        "body", parent=base["BodyText"], textColor=INK, fontSize=9.5, leading=13, spaceAfter=4
    )
    soft = ParagraphStyle(
        "soft", parent=body, textColor=INK_SOFT, fontSize=9, leading=12
    )
    label = ParagraphStyle(
        "label",
        parent=base["Normal"],
        textColor=INK_FAINT,
        fontSize=7.5,
        fontName="Helvetica-Bold",
        leading=10,
    )
    return {"title": title, "eyebrow": eyebrow, "h2": h2, "h3": h3, "body": body, "soft": soft, "label": label}


def render_briefing_pdf(
    patient: PatientProfile,
    match: MatchResponse,
    coordinator_email: Optional[str] = None,
) -> bytes:
    """Render the briefing PDF and return raw bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="Clinical Trial Briefing — TrialFinder",
        author="TrialFinder",
    )

    s = _styles()
    story = []

    # --- Header ---
    story.append(Paragraph("CLINICAL TRIAL BRIEFING", s["eyebrow"]))
    story.append(Paragraph("Top-matched trials for physician review", s["title"]))
    story.append(Paragraph(
        f"Prepared {datetime.utcnow().strftime('%B %d, %Y')} by TrialFinder",
        s["soft"],
    ))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#e3e9f0"), spaceBefore=8, spaceAfter=8))

    # --- Patient summary ---
    story.append(Paragraph("Patient summary", s["h2"]))
    summary_rows = []
    summary_rows.append(["Condition", patient.condition])
    if patient.treatment_history:
        summary_rows.append(["Treatment history", patient.treatment_history])
    summary_rows.append(["Location", patient.location])
    if patient.age is not None:
        summary_rows.append(["Age", str(patient.age)])
    if patient.medications:
        summary_rows.append(["Medications", ", ".join(patient.medications)])
    if patient.biomarkers:
        summary_rows.append(["Biomarkers", ", ".join(patient.biomarkers)])
    if patient.last_treatment_date:
        summary_rows.append(["Last treatment", patient.last_treatment_date])
    if patient.additional_context:
        summary_rows.append(["Notes", patient.additional_context])

    table = Table(
        [[Paragraph(k, s["label"]), Paragraph(_esc(v), s["body"])] for k, v in summary_rows],
        colWidths=[1.3 * inch, 5.5 * inch],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e3e9f0")),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.18 * inch))

    # --- Top 3 trials ---
    story.append(Paragraph("Top 3 trial matches", s["h2"]))
    story.append(Spacer(1, 0.05 * inch))

    top = match.trials[:3]
    for i, t in enumerate(top):
        _render_trial(story, s, i + 1, t)
        if i < len(top) - 1:
            story.append(HRFlowable(width="100%", thickness=0.3, color=colors.HexColor("#e3e9f0"), spaceBefore=6, spaceAfter=6))

    # --- Footer ---
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e3e9f0"), spaceBefore=4, spaceAfter=6))
    if coordinator_email:
        story.append(Paragraph(f"<b>Patient contact:</b> {coordinator_email}", s["soft"]))
    story.append(Paragraph(
        "This briefing is informational and is not medical advice. Trial eligibility "
        "must be confirmed by the trial's study team. Generated by TrialFinder.",
        s["soft"],
    ))

    doc.build(story)
    return buf.getvalue()


def _render_trial(story: list, s: dict, rank: int, t: RankedTrial) -> None:
    # Header line with rank, fit score, phase, status
    pills = []
    if t.phase:
        pills.append(t.phase)
    if t.status:
        pills.append(t.status)
    if t.intervention_type:
        pills.append(t.intervention_type)
    pill_line = " · ".join(pills) if pills else ""

    title_para = Paragraph(
        f"<b>#{rank} · Fit {t.fit_score}/100</b> &nbsp; "
        f"<font color='#7d8b99'>{_esc(pill_line)}</font>",
        s["body"],
    )
    story.append(title_para)
    story.append(Paragraph(f"<b>{_esc(t.title)}</b>", s["h3"]))
    if t.nct_id:
        story.append(Paragraph(_esc(t.nct_id), s["soft"]))

    if t.why_this_fits:
        story.append(Spacer(1, 0.06 * inch))
        story.append(Paragraph("<b>Why this fits</b>", s["label"]))
        story.append(Paragraph(_esc(t.why_this_fits), s["body"]))

    if t.biomarker_match:
        story.append(Paragraph("<b>Biomarker fit</b>", s["label"]))
        story.append(Paragraph(_esc(t.biomarker_match), s["body"]))

    if t.eligibility_summary:
        story.append(Paragraph("<b>Eligibility</b>", s["label"]))
        story.append(Paragraph(_esc(t.eligibility_summary), s["body"]))

    if t.warning_flags:
        story.append(Paragraph("<b>Potential contraindications</b>", s["label"]))
        for flag in t.warning_flags:
            story.append(Paragraph(f"• {_esc(flag)}", s["body"]))

    if t.washout_weeks is not None:
        washout = (
            "No washout required (available now)" if t.washout_weeks == 0
            else f"{t.washout_weeks}-week washout required"
            + (f"; earliest enrollable {t.earliest_enrollable_date}" if t.earliest_enrollable_date else "")
        )
        story.append(Paragraph("<b>Washout</b>", s["label"]))
        story.append(Paragraph(_esc(washout), s["body"]))

    meta_bits = []
    if t.sponsor:
        meta_bits.append(f"<b>Sponsor:</b> {_esc(t.sponsor)}")
    if t.location:
        meta_bits.append(f"<b>Location:</b> {_esc(t.location)}")
    if t.source_url:
        meta_bits.append(
            f"<b>Listing:</b> <link href='{_esc(t.source_url)}' color='#1f6feb'>{_esc(t.source_url)}</link>"
        )
    if meta_bits:
        story.append(Spacer(1, 0.04 * inch))
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(meta_bits), s["soft"]))


def _esc(value) -> str:
    if value is None:
        return ""
    s = str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
