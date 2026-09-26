"""A4-faktura med ReportLab. Ingen avhengighet til brukergrensesnittet."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import money


def make_copy(original):
    """Legg KOPI på hver side av originalen, uten å bygge fakturaen på nytt."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(original))
    writer = PdfWriter()
    for page in reader.pages:
        copy_page = writer.add_page(page)
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        stamp = BytesIO()
        canvas = Canvas(stamp, pagesize=(width, height))
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawRightString(width - 20 * mm, height - 10 * mm, "KOPI")
        canvas.save()
        copy_page.merge_page(PdfReader(BytesIO(stamp.getvalue())).pages[0])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_pdf(details, number, logo=None):
    output = BytesIO()
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    def paragraph(text):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), normal)

    story = []
    if logo:
        image = Image(BytesIO(logo))
        scale = min(45 * mm / image.imageWidth, 22 * mm / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        image.hAlign = "LEFT"
        story.extend([image, Spacer(1, 5 * mm)])
    seller = details["seller"]
    customer = details["customer"]
    seller_text = f"{seller['name']}\n{seller['address']}\n{seller['postal_code']} {seller['city']}\nOrg.nr. {seller['org_number']}"
    if seller["mva"]:
        seller_text += " MVA"
    seller_text += f"\n{seller['email']}\n{seller['phone']}"
    heading = "BETALINGSPÅMINNELSE" if details.get("reminder") else "FAKTURA"
    story.append(Paragraph(heading, styles["Title"]))
    header = Table([[paragraph(seller_text), paragraph(
        f"Fakturanummer: {number}\nFakturadato: {details['date']}\nForfall: {details['due']}\nKundenummer: {customer['id']}")]], colWidths=[100 * mm, 70 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([header, Spacer(1, 10 * mm)])
    buyer = f"Til: {customer['name']}\n{customer['address']}\n{customer['postal_code']} {customer['city']}\n{customer['country']}"
    if customer["org_number"]:
        buyer += f"\nOrg.nr. {customer['org_number']}"
    story.extend([paragraph(buyer), Spacer(1, 5 * mm), paragraph(
        f"Levering: {details['delivery_date']} – {details['delivery_place']}"),
        paragraph(f"Deres referanse: {details.get('reference', '')}"), Spacer(1, 6 * mm)])
    rows = [["Beskrivelse", "Antall", "Pris eks. MVA", "MVA-type", "Netto"]]
    for line in details["lines"]:
        rows.append([paragraph(line["description"]), paragraph(f"{line['quantity']} {line['unit']}"),
                     money(line["price"]), paragraph(line["vat"]), money(line["net"])])
    table = Table(rows, colWidths=[59 * mm, 22 * mm, 29 * mm, 33 * mm, 27 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 8 * mm)])
    story.append(paragraph(f"Netto: {money(details['net'])} kr"))
    for vat in dict.fromkeys(line["vat"] for line in details["lines"]):
        tax = sum(line["tax"] for line in details["lines"] if line["vat"] == vat)
        story.append(paragraph(f"MVA {vat}: {money(tax)} kr"))
    story.append(Paragraph(f"Totalt: {money(details['net'] + details['tax'])} kr", styles["Heading2"]))
    if details.get("reminder"):
        story.append(paragraph(f"Gjenstående å betale: {money(details['remaining'])} kr"))
    story.append(paragraph(f"Betal til konto {seller['account']}. Oppgi fakturanummer {number}."))
    if details.get("note"):
        story.extend([Spacer(1, 5 * mm), paragraph(details["note"])])

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.drawString(20 * mm, 12 * mm, f"Faktura {number}")
        canvas.drawRightString(190 * mm, 12 * mm, f"Side {doc.page}")

    SimpleDocTemplate(output, rightMargin=20 * mm, leftMargin=20 * mm,
                      topMargin=16 * mm, bottomMargin=22 * mm).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
