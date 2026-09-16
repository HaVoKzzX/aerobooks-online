"""Professional invoice PDF generation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from aerobooks import branding, db
from aerobooks.money import fmt_date, fmt_money, money

NAVY = colors.HexColor("#1B365D")
GOLD = colors.HexColor("#C4A35A")
SLATE = colors.HexColor("#4A5568")
LINE = colors.HexColor("#D6D3CD")
BG = colors.HexColor("#F7F5F0")
RED = colors.HexColor("#9B2C2C")


def venmo_payment_url(username: str, amount: float | None = None, note: str = "") -> str:
    user = (username or "").lstrip("@").strip()
    if not user:
        return ""
    url = f"https://venmo.com/{quote(user)}"
    params = []
    params.append("txn=pay")
    if amount and amount > 0:
        params.append(f"amount={amount:.2f}")
    if note:
        params.append(f"note={quote(note)}")
    if params:
        url += "?" + "&".join(params)
    return url


def generate_qr_png(url: str, dest: Path, box_size: int = 8) -> Path | None:
    if not url:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1B365D", back_color="white")
    from io import BytesIO

    from aerobooks.store import secure_write

    buf = BytesIO()
    img.save(buf, format="PNG")
    secure_write(dest, buf.getvalue())
    return dest


def settings_qr_path() -> Path | None:
    s = db.get_settings()
    custom = (s.get("custom_qr_path") or "").strip()
    if custom and Path(custom).exists():
        return Path(custom)
    username = (s.get("venmo_username") or "").lstrip("@").strip()
    if not username:
        return None
    dest = db.QR_DIR / f"venmo_{username}.png"
    url = venmo_payment_url(username)
    return generate_qr_png(url, dest)


def invoice_qr_path(invoice: dict) -> Path | None:
    s = db.get_settings()
    custom = (s.get("custom_qr_path") or "").strip()
    if custom and Path(custom).exists():
        return Path(custom)
    username = (s.get("venmo_username") or "").lstrip("@").strip()
    if not username:
        return None
    note_prefix = s.get("venmo_note_prefix") or "Flight training"
    note = f"{note_prefix} {invoice['number']}"
    amount = money(invoice.get("balance") or invoice.get("total"))
    url = venmo_payment_url(username, amount, note)
    dest = db.QR_DIR / f"invoice_{invoice['id']}.png"
    return generate_qr_png(url, dest)


def _styles():
    base = getSampleStyleSheet()
    styles = {
        "brand": ParagraphStyle(
            "brand",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=NAVY,
        ),
        "instructor": ParagraphStyle(
            "instructor",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=10,
            leading=13,
            textColor=SLATE,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=SLATE,
        ),
        "small_right": ParagraphStyle(
            "small_right",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=SLATE,
            alignment=TA_RIGHT,
        ),
        "meta_label": ParagraphStyle(
            "meta_label",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=SLATE,
            alignment=TA_RIGHT,
        ),
        "meta_value": ParagraphStyle(
            "meta_value",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            alignment=TA_RIGHT,
        ),
        "invoice_word": ParagraphStyle(
            "invoice_word",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=GOLD,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1A1A1A"),
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "td": ParagraphStyle(
            "td",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1A1A1A"),
        ),
        "td_right": ParagraphStyle(
            "td_right",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#1A1A1A"),
        ),
        "td_right_b": ParagraphStyle(
            "td_right_b",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=NAVY,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=SLATE,
        ),
        "paid": ParagraphStyle(
            "paid",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1B7A4E"),
            alignment=TA_CENTER,
        ),
        "overdue": ParagraphStyle(
            "overdue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=RED,
            alignment=TA_RIGHT,
        ),
    }
    return styles


def _esc(text) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _address_block(s: dict) -> str:
    lines = []
    certs = []
    if s.get("cfi_number"):
        certs.append(f"CFI {_esc(s['cfi_number'])}")
    if s.get("cfii_number"):
        certs.append(f"CFII {_esc(s['cfii_number'])}")
    if certs:
        lines.append(" · ".join(certs))
    if s.get("address"):
        lines.append(_esc(s["address"]))
    city_line = " ".join(p for p in [s.get("city"), s.get("state"), s.get("zip")] if p)
    if city_line:
        lines.append(_esc(city_line))
    contact = []
    if s.get("phone"):
        contact.append(_esc(s["phone"]))
    if s.get("email"):
        contact.append(_esc(s["email"]))
    if s.get("website"):
        contact.append(_esc(s["website"]))
    if contact:
        lines.append(" · ".join(contact))
    if s.get("home_airport"):
        lines.append(f"Home airport: {_esc(s['home_airport'])}")
    return "<br/>".join(lines)


def _bill_to(inv: dict) -> str:
    lines = [f"<b>{_esc(inv.get('student_name'))}</b>"]
    if inv.get("student_address"):
        lines.append(_esc(inv["student_address"]))
    city_line = " ".join(
        p for p in [inv.get("student_city"), inv.get("student_state"), inv.get("student_zip")] if p
    )
    if city_line:
        lines.append(_esc(city_line))
    contact = []
    if inv.get("student_email"):
        contact.append(_esc(inv["student_email"]))
    if inv.get("student_phone"):
        contact.append(_esc(inv["student_phone"]))
    if contact:
        lines.append(" · ".join(contact))
    return "<br/>".join(lines)


def build_invoice_pdf(invoice_id: int) -> Path:
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    s = db.get_settings()
    styles = _styles()
    db.INVOICE_DIR.mkdir(parents=True, exist_ok=True)
    dest = db.INVOICE_DIR / f"{inv['number']}.pdf"
    buffer = BytesIO()
    temps: list[Path] = []

    def readable(path: Path | None) -> Path | None:
        if not path or not Path(path).exists():
            return path
        from aerobooks.crypto import is_encrypted
        from aerobooks.store import decrypt_to_temp

        candidate = Path(path)
        if is_encrypted(candidate.read_bytes()):
            tmp = decrypt_to_temp(candidate)
            temps.append(tmp)
            return tmp
        return candidate

    brand = s.get("business_name") if s.get("entity_type") == "business" and s.get("business_name") else s.get("instructor_name") or "Flight Instruction"
    instructor_line = ""
    if s.get("entity_type") == "business" and s.get("business_name") and s.get("instructor_name"):
        instructor_line = f"Certified Flight Instructor — {_esc(s['instructor_name'])}"
    elif s.get("instructor_name"):
        instructor_line = "Certified Flight Instructor"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Invoice {inv['number']}",
        author=brand,
    )

    story = []

    left_head = [
        Paragraph(_esc(brand), styles["brand"]),
    ]
    if instructor_line:
        left_head.append(Paragraph(instructor_line, styles["instructor"]))
    left_head.append(Spacer(1, 4))
    left_head.append(Paragraph(_address_block(s), styles["small"]))

    right_cells = [
        [Paragraph("INVOICE", styles["invoice_word"])],
        [Paragraph(_esc(inv["number"]), styles["meta_value"])],
        [Paragraph(f"Issued {fmt_date(inv['issue_date'])}", styles["meta_label"])],
        [Paragraph(f"Due {fmt_date(inv['due_date'])}", styles["meta_label"])],
    ]
    if inv.get("display_status") == "overdue":
        days = inv.get("days_overdue") or 0
        right_cells.append([Paragraph(f"OVERDUE — {days} days", styles["overdue"])])
    elif inv.get("status") == "paid":
        right_cells.append([Paragraph("PAID", styles["paid"])])

    right = Table(right_cells, colWidths=[2.45 * inch])
    right.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    logo_path = branding.logo_png_path()
    mark = Image(str(logo_path), width=0.40 * inch, height=0.40 * inch)
    header = Table([[mark, left_head, right]], colWidths=[0.50 * inch, 4.25 * inch, 2.45 * inch])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "TOP"),
                ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                ("VALIGN", (2, 0), (2, 0), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 6),
                ("TOPPADDING", (0, 0), (0, 0), 1),
                ("LEFTPADDING", (1, 0), (1, 0), 2),
                ("RIGHTPADDING", (1, 0), (1, 0), 8),
                ("LEFTPADDING", (2, 0), (2, 0), 0),
                ("RIGHTPADDING", (2, 0), (2, 0), 0),
                ("TOPPADDING", (1, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=2))
    story.append(HRFlowable(width="100%", thickness=0.6, color=GOLD, spaceBefore=0, spaceAfter=12))

    bill = Table(
        [
            [
                Paragraph("BILL TO", styles["section"]),
                Paragraph("STATUS", styles["section"]),
            ],
            [
                Paragraph(_bill_to(inv), styles["body"]),
                Paragraph(
                    f"{_esc((inv.get('display_status') or inv['status']).replace('_', ' ').title())}<br/>"
                    f"Balance due: <b>{fmt_money(inv['balance'])}</b>",
                    styles["body"],
                ),
            ],
        ],
        colWidths=[4.6 * inch, 2.6 * inch],
    )
    bill.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BACKGROUND", (0, 1), (-1, 1), BG),
                ("LEFTPADDING", (0, 1), (-1, 1), 8),
                ("RIGHTPADDING", (0, 1), (-1, 1), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
            ]
        )
    )
    story.append(bill)
    story.append(Spacer(1, 16))

    th = styles["th"]
    td = styles["td"]
    tdr = styles["td_right"]
    rows = [
        [
            Paragraph("Description", th),
            Paragraph("Qty", th),
            Paragraph("Unit", th),
            Paragraph("Rate", th),
            Paragraph("Amount", th),
        ]
    ]
    for item in inv.get("items") or []:
        unit = item.get("unit") or ""
        rows.append(
            [
                Paragraph(_esc(item.get("description")), td),
                Paragraph(f"{float(item.get('quantity') or 0):.1f}".rstrip("0").rstrip("."), tdr),
                Paragraph(_esc(unit), td),
                Paragraph(fmt_money(item.get("unit_price")), tdr),
                Paragraph(fmt_money(item.get("amount")), tdr),
            ]
        )
    if len(rows) == 1:
        rows.append(
            [
                Paragraph("No line items", td),
                Paragraph("", tdr),
                Paragraph("", td),
                Paragraph("", tdr),
                Paragraph(fmt_money(0), tdr),
            ]
        )

    items_table = Table(rows, colWidths=[3.7 * inch, 0.7 * inch, 0.8 * inch, 1.0 * inch, 1.0 * inch], repeatRows=1)
    item_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            item_style.append(("BACKGROUND", (0, i), (-1, i), BG))
    items_table.setStyle(TableStyle(item_style))
    story.append(items_table)
    story.append(Spacer(1, 12))

    totals = []
    totals.append([Paragraph("Subtotal", styles["small_right"]), Paragraph(fmt_money(inv["subtotal"]), tdr)])
    if money(inv.get("discount_amount")) > 0:
        label = "Discount"
        if inv.get("discount_type") == "percent":
            label = f"Discount ({float(inv.get('discount_value') or 0):.1f}%)"
        totals.append([Paragraph(label, styles["small_right"]), Paragraph(f"-{fmt_money(inv['discount_amount'])}", tdr)])
    if money(inv.get("tax_amount")) > 0:
        tax_label = s.get("tax_label") or "Tax"
        totals.append(
            [
                Paragraph(f"{_esc(tax_label)} ({float(inv.get('tax_rate') or 0):.2f}%)", styles["small_right"]),
                Paragraph(fmt_money(inv["tax_amount"]), tdr),
            ]
        )
    totals.append([Paragraph("Total", styles["td_right_b"]), Paragraph(fmt_money(inv["total"]), styles["td_right_b"])])
    if money(inv.get("amount_paid")) > 0:
        totals.append([Paragraph("Paid", styles["small_right"]), Paragraph(fmt_money(inv["amount_paid"]), tdr)])
    totals.append([Paragraph("Balance due", styles["td_right_b"]), Paragraph(fmt_money(inv["balance"]), styles["td_right_b"])])

    totals_table = Table(totals, colWidths=[1.6 * inch, 1.1 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, -1), (-1, -1), BG),
            ]
        )
    )

    pay_bits = []
    if inv.get("include_venmo") and (s.get("venmo_username") or s.get("custom_qr_path")):
        username = (s.get("venmo_username") or "").lstrip("@")
        qr_file = invoice_qr_path(inv)
        pay_flow = [Paragraph("PAY WITH VENMO", styles["section"])]
        if username:
            pay_flow.append(Paragraph(f"@{_esc(username)}", styles["body"]))
        qr_src = readable(qr_file)
        if qr_src and qr_src.exists():
            pay_flow.append(Spacer(1, 6))
            pay_flow.append(Image(str(qr_src), width=1.35 * inch, height=1.35 * inch))
            pay_flow.append(Paragraph("Scan to pay this invoice", styles["footer"]))
        pay_bits = pay_flow
    else:
        pay_bits = [Paragraph(" ", styles["body"])]

    bottom = Table([[pay_bits, totals_table]], colWidths=[4.5 * inch, 2.7 * inch])
    bottom.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(bottom)

    if inv.get("notes"):
        story.append(Spacer(1, 14))
        story.append(Paragraph("NOTES", styles["section"]))
        story.append(Paragraph(_esc(inv["notes"]).replace("\n", "<br/>"), styles["body"]))
    if inv.get("terms"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("TERMS", styles["section"]))
        story.append(Paragraph(_esc(inv["terms"]).replace("\n", "<br/>"), styles["footer"]))

    payments = inv.get("payments") or []
    if payments:
        story.append(Spacer(1, 10))
        story.append(Paragraph("PAYMENTS RECEIVED", styles["section"]))
        for p in payments:
            story.append(
                Paragraph(
                    f"{fmt_date(p['date'])} — {fmt_money(p['amount'])} via {_esc(p.get('method'))}"
                    + (f" ({_esc(p.get('reference'))})" if p.get("reference") else ""),
                    styles["footer"],
                )
            )

    def _on_page(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(3)
        canvas.line(0.65 * inch, 0.38 * inch, 8.05 * inch, 0.38 * inch)
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(0.65 * inch, 0.22 * inch, f"{brand}  ·  Invoice {inv['number']}")
        canvas.drawRightString(8.05 * inch, 0.22 * inch, "Generated by AeroBooks")
        canvas.restoreState()

    try:
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        from aerobooks.store import secure_write

        secure_write(dest, buffer.getvalue())
    finally:
        for tmp in temps:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    return dest


def invoice_pdf_bytes(invoice_id: int) -> tuple[str, bytes]:
    from aerobooks.store import secure_read

    path = build_invoice_pdf(invoice_id)
    return path.name, secure_read(path)
