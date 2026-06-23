"""Generate the Tungaloy re-engagement call script as a PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 HRFlowable, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

OUTPUT = "call_script_no_order_q1_2026_v4.pdf"

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2*cm, bottomMargin=2*cm,
)

TUNGALOY_RED = colors.HexColor("#c0392b")
DARK         = colors.HexColor("#1a1a1a")
MID          = colors.HexColor("#555555")
LIGHT_GREY   = colors.HexColor("#f5f5f5")
BORDER_GREY  = colors.HexColor("#dddddd")

styles = getSampleStyleSheet()

title_style = ParagraphStyle("title",
    fontSize=20, textColor=TUNGALOY_RED, fontName="Helvetica-Bold",
    spaceAfter=4, alignment=TA_CENTER)

subtitle_style = ParagraphStyle("subtitle",
    fontSize=11, textColor=MID, fontName="Helvetica",
    spaceAfter=2, alignment=TA_CENTER)

section_style = ParagraphStyle("section",
    fontSize=12, textColor=colors.white, fontName="Helvetica-Bold",
    spaceBefore=10, spaceAfter=6, leftIndent=0)

body_style = ParagraphStyle("body",
    fontSize=10, textColor=DARK, fontName="Helvetica",
    leading=16, spaceAfter=4, leftIndent=0)

quote_style = ParagraphStyle("quote",
    fontSize=10, textColor=DARK, fontName="Helvetica-Oblique",
    leading=16, spaceAfter=4, leftIndent=12,
    borderPadding=(6, 10, 6, 10))

note_style = ParagraphStyle("note",
    fontSize=9, textColor=MID, fontName="Helvetica-Oblique",
    leading=14, spaceAfter=4, leftIndent=12)

bullet_style = ParagraphStyle("bullet",
    fontSize=10, textColor=DARK, fontName="Helvetica",
    leading=16, spaceAfter=2, leftIndent=20, bulletIndent=10)


def section_header(text):
    """Red header bar as a single-cell table."""
    tbl = Table([[Paragraph(text, ParagraphStyle("sh",
        fontSize=11, textColor=colors.white, fontName="Helvetica-Bold"))]],
        colWidths=[17*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), TUNGALOY_RED),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return tbl


def quote_box(lines):
    """Light-grey box for spoken lines."""
    content = "<br/>".join(lines)
    tbl = Table([[Paragraph(content, quote_style)]], colWidths=[17*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_GREY),
        ("BOX",           (0,0), (-1,-1), 1, BORDER_GREY),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return tbl


story = []

# ── Title ─────────────────────────────────────────────────────────────────────
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph("Tungaloy UK", title_style))
story.append(Paragraph("Re-engagement Call Script", subtitle_style))
story.append(Paragraph("No Order Q1 2026", ParagraphStyle("sub2",
    fontSize=10, textColor=TUNGALOY_RED, fontName="Helvetica-Bold",
    spaceAfter=10, alignment=TA_CENTER)))
story.append(HRFlowable(width="100%", thickness=1.5, color=TUNGALOY_RED, spaceAfter=12))

# ── Opening ───────────────────────────────────────────────────────────────────
story.append(section_header("📞  Opening"))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"Hi, could I speak to <b>[Contact Name]</b> please?',
    '… Hi [Name], it\'s <b>[Your Name]</b> calling from Tungaloy UK.',
    'How are you doing? How\'s business at the moment?"',
]))
story.append(Paragraph("(Let them talk. Acknowledge before moving on.)", note_style))
story.append(Spacer(1, 0.3*cm))

# ── Check-in ──────────────────────────────────────────────────────────────────
story.append(section_header("🔍  The Check-in"))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"The reason I\'m calling is that we haven\'t seen an order from you for a little while,',
    'and I just wanted to check in — we don\'t want to lose touch."',
]))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"Are you still using Tungaloy tooling, or have you switched away from us?"',
]))
story.append(Spacer(1, 0.3*cm))

# ── Branch A ──────────────────────────────────────────────────────────────────
story.append(section_header("🛒  Branch A — Buying Through a Distributor"))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"Ah okay, which distributor are you using at the moment?',
    '… Are they visiting you regularly?',
    '… And do you have a vending machine on site?"',
]))
story.append(Paragraph(
    "(Note the distributor name, visit frequency, and vending machine — log in Sales Navigator after the call.)",
    note_style))
story.append(Spacer(1, 0.15*cm))
story.append(quote_box([
    '"That\'s useful to know. We do work closely with our distribution partners,',
    'so it\'s worth us staying in touch directly too — just so you know what\'s available',
    'and we can make sure you\'re getting the right support."',
]))
story.append(Spacer(1, 0.3*cm))

# ── Branch B ──────────────────────────────────────────────────────────────────
story.append(section_header("🔄  Branch B — Stopped Using Tungaloy / Switched Supplier"))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"Oh that\'s a shame to hear — can I ask what prompted the change?"',
]))
story.append(Paragraph("(Listen. Don't push back immediately.)", note_style))
story.append(Spacer(1, 0.15*cm))
story.append(quote_box([
    '"I completely understand. I did want to mention one thing though —',
    'as you\'ll probably be aware, carbide prices have been rising across the board,',
    'and like everyone else we do have a <b>price increase coming on 1st May</b>."',
    '',
    '"However — and this is the reason I\'m calling now — we\'ve had approval to',
    '<b>hold current prices on any orders placed this month, right through until the end of 2026</b>.',
    'So there\'s actually a real saving to be made if the timing works."',
    '',
    '"Are there any tools or inserts you\'re going through regularly?',
    'Even if it\'s a competitor product — I\'d love to see if we can put together',
    'a Tungaloy alternative and give you a quote."',
]))
story.append(Spacer(1, 0.3*cm))

# ── Close ─────────────────────────────────────────────────────────────────────
story.append(section_header("✅  Close"))
story.append(Spacer(1, 0.2*cm))
story.append(quote_box([
    '"I\'ll leave that with you — I don\'t want to take up too much of your time.',
    'Would it be okay if I send you a quick email with a couple of our current offers?',
    'Just so you\'ve got something to refer back to."',
    '',
    '"And would it be worth one of our reps popping in to see you?',
    'Even just for a quick catch-up — no pressure at all."',
]))
story.append(Spacer(1, 0.3*cm))

# ── Log it ────────────────────────────────────────────────────────────────────
story.append(section_header("📋  After Every Call — Two Things to Do"))
story.append(Spacer(1, 0.2*cm))

story.append(Paragraph("<b>1.  Add a Note in Less Annoying CRM (LACRM)</b>", ParagraphStyle("step",
    fontSize=10, textColor=DARK, fontName="Helvetica-Bold", leading=16, spaceAfter=4)))
story.append(Paragraph(
    "Find the contact in LACRM and add a note with the following details:", body_style))

log_items = [
    "Outcome: still using Tungaloy / buying via distributor / switched to competitor / not interested",
    "Distributor name (if buying through one)",
    "Do they have a vending machine on site?  Yes / No",
    "Items or products discussed",
    "Agreed follow-up action: email / rep visit / send quote / no action needed",
]
for item in log_items:
    story.append(Paragraph(f"• {item}", bullet_style))

story.append(Spacer(1, 0.25*cm))

story.append(Paragraph("<b>2.  Email a Summary to Rob Werhun</b>", ParagraphStyle("step",
    fontSize=10, textColor=DARK, fontName="Helvetica-Bold", leading=16, spaceAfter=4)))
story.append(Paragraph(
    "After each call (or at the end of each session), send a quick email to:", body_style))
story.append(Paragraph(
    "📧  <b>rob.werhun@tungaloyuk.co.uk</b>", ParagraphStyle("email",
    fontSize=10, textColor=TUNGALOY_RED, fontName="Helvetica-Bold",
    leading=16, spaceAfter=6, leftIndent=20)))
story.append(Paragraph("Include for each customer:", body_style))

email_items = [
    "Company name &amp; contact name",
    "Outcome of the call",
    "Distributor used (if applicable) + vending machine Y/N",
    "Any products or quotes requested",
    "What follow-up (if any) is needed from Rob or the sales team",
]
for item in email_items:
    story.append(Paragraph(f"• {item}", bullet_style))

story.append(Spacer(1, 0.4*cm))
story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GREY, spaceAfter=6))
story.append(Paragraph(
    "Tungaloy UK  |  Price hold valid on orders placed before 30 April 2026  |  rob.werhun@tungaloyuk.co.uk",
    ParagraphStyle("footer", fontSize=8, textColor=MID, fontName="Helvetica", alignment=TA_CENTER)))

doc.build(story)
print(f"PDF saved: {OUTPUT}")
