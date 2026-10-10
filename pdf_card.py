"""pdf_card.py - Beautiful printable field card using ReportLab.

Generates a single-page A5-ish pocket field card with:
- Best window & conditions
- Nudge message
- 3 things to notice
- 3 things to pack
- Leave-phone tip
- Blank journal lines for handwritten notes
"""

from __future__ import annotations

import io
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ─── Custom Flowable: dotted journal line ─────────────────────────────────────
class JournalLine(Flowable):
    """A single dotted line for handwritten notes on the field card."""

    def __init__(self, width: float, color: colors.Color = colors.Color(0.78, 0.75, 0.70)):
        super().__init__()
        self.line_width = width
        self.line_color = color
        self.height = 8 * mm

    def draw(self):
        self.canv.setStrokeColor(self.line_color)
        self.canv.setDash(1, 3)
        self.canv.setLineWidth(0.4)
        self.canv.line(0, 2 * mm, self.line_width, 2 * mm)


# ─── Styles ───────────────────────────────────────────────────────────────────

SAGE = colors.Color(0.29, 0.49, 0.35)  # #4A7C59
DARK = colors.Color(0.17, 0.17, 0.17)  # #2C2C2C
WARM_BG = colors.Color(0.99, 0.98, 0.96)  # #FDFAF6
MUTED = colors.Color(0.55, 0.52, 0.48)  # #8C8578


def _build_styles() -> Dict[str, ParagraphStyle]:
    """Build custom paragraph styles for the field card."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CardTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=SAGE,
            spaceAfter=3 * mm,
            alignment=1, # center
        ),
        "subtitle": ParagraphStyle(
            "CardSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=5 * mm,
            alignment=1, # center
        ),
        "nudge": ParagraphStyle(
            "Nudge",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=DARK,
            spaceAfter=4 * mm,
            alignment=1, # center
        ),
        "section_head": ParagraphStyle(
            "SectionHead",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=SAGE,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=DARK,
        ),
        "phone_tip": ParagraphStyle(
            "PhoneTip",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceBefore=4 * mm,
            alignment=1, # center
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=MUTED,
            alignment=1,  # center
        ),
    }


# ─── Card Generator ──────────────────────────────────────────────────────────

def generate_field_card(
    window: Dict[str, Any],
    nudge_data: Dict[str, Any],
    location: str = "My spot",
    date_str: str = "",
) -> bytes:
    """
    Generate a printable A5 field card as a PDF byte string.

    Args:
        window: Ranked window dict with weather features and predictions.
        nudge_data: Output from nudge.generate_nudge().
        location: Location name.
        date_str: Human-readable date string.

    Returns:
        PDF content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A5,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=8 * mm,
    )

    styles = _build_styles()
    story = []
    usable_width = A5[0] - 24 * mm

    # ── Header ──
    story.append(Paragraph("🌿 Grassday Field Card", styles["title"]))
    subtitle = f"{location}  ·  {date_str}" if date_str else location
    story.append(Paragraph(subtitle, styles["subtitle"]))

    # ── Best Window ──
    temp = window.get("temperature_2m", "?")
    feels = window.get("apparent_temperature", "?")
    wind = window.get("wind_speed_10m", "?")
    rain = window.get("precipitation", 0)
    uv = window.get("uv_index", "?")
    score = window.get("predicted", "?")
    start = str(window.get("window_start", "?"))
    end = str(window.get("window_end", "?"))

    # Extract time portion
    start_time = start.split("T")[-1][:5] if "T" in start else start
    end_time = end.split("T")[-1][:5] if "T" in end else end

    conditions_data = [
        ["🕐 Window", f"{start_time} – {end_time}"],
        ["🌡️ Temp", f"{temp}°C (feels {feels}°C)"],
        ["💨 Wind", f"{wind} km/h"],
        ["🌧️ Rain", f"{rain} mm"],
        ["☀️ UV", f"{uv}"],
        ["⭐ Score", f"{score}/5"],
    ]
    cond_table = Table(conditions_data, colWidths=[usable_width * 0.35, usable_width * 0.65])
    cond_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), SAGE),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cond_table)
    story.append(Spacer(1, 3 * mm))

    # ── Nudge ──
    nudge_text = nudge_data.get("nudge", "Time to go outside.")
    story.append(Paragraph(f'"{nudge_text}"', styles["nudge"]))

    # ── Notice (3 things to look for) ──
    story.append(Paragraph("👀 LOOK FOR", styles["section_head"]))
    for item in nudge_data.get("notice", [])[:3]:
        story.append(Paragraph(f"• {item}", styles["body"]))

    # ── Pack (3 things to bring) ──
    story.append(Paragraph("🎒 PACK", styles["section_head"]))
    for item in nudge_data.get("pack", [])[:3]:
        story.append(Paragraph(f"• {item}", styles["body"]))

    # ── Phone tip ──
    phone_tip = nudge_data.get("leave_phone_tip", "Leave the phone behind.")
    story.append(Paragraph(f"📵 {phone_tip}", styles["phone_tip"]))

    # ── Journal lines ──
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("✏️ FIELD NOTES", styles["section_head"]))
    for _ in range(6):
        story.append(JournalLine(usable_width))

    # ── Footer ──
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Grassday · Touch Grass · Put the phone down · Go outside",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
