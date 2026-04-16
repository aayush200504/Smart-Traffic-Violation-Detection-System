import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime, timedelta
from io import BytesIO

FINES_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'fines')

def get_qr(data):
    from PIL import Image as PILImage, ImageDraw
    img = PILImage.new('RGB', (120, 120), color='white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([5,5,115,115], outline='black', width=3)
    draw.rectangle([15,15,45,45], fill='black')
    draw.rectangle([75,15,105,45], fill='black')
    draw.rectangle([15,75,45,105], fill='black')
    draw.rectangle([55,55,85,85], fill='black')
    draw.text((40, 52), "PAY", fill='black')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_fine_pdf(violation_id, plate_number, owner_data, violation_info, image_path, paid=False):
    os.makedirs(FINES_DIR, exist_ok=True)
    pdf_path = os.path.join(FINES_DIR, f'{violation_id}.pdf')

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)

    NAVY       = colors.HexColor('#0A1628')
    BLUE       = colors.HexColor('#1E3A8A')
    RED        = colors.HexColor('#DC2626')
    GREEN      = colors.HexColor('#16A34A')
    LIGHT_GRAY = colors.HexColor('#F8FAFC')
    MID_GRAY   = colors.HexColor('#64748B')
    BORDER     = colors.HexColor('#E2E8F0')

    severity_colors = {
        'Low':      colors.HexColor('#16A34A'),
        'Medium':   colors.HexColor('#D97706'),
        'High':     colors.HexColor('#DC2626'),
        'Critical': colors.HexColor('#7C3AED'),
    }

    severity  = dict(violation_info).get('severity', 'Medium')
    sev_color = severity_colors.get(severity, RED)
    styles    = getSampleStyleSheet()

    def style(name='Normal', **kwargs):
        return ParagraphStyle(name, parent=styles[name], **kwargs)

    story = []

    # ── HEADER ──────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<font color="white"><b>GOVERNMENT OF INDIA</b><br/>'
                  'Ministry of Road Transport &amp; Highways<br/>'
                  'Traffic Enforcement Division</font>',
                  style(fontSize=9, textColor=colors.white, alignment=TA_LEFT, leading=14)),
        Paragraph('<font color="#F59E0B"><b>e-CHALLAN</b></font><br/>'
                  '<font color="white" size="8">Digital Traffic Fine</font>',
                  style(fontSize=20, textColor=colors.white, alignment=TA_RIGHT, leading=24)),
    ]]
    header_table = Table(header_data, colWidths=[100*mm, 80*mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('PADDING',    (0,0), (-1,-1), 12),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4*mm))

    # ── ALERT BAR ───────────────────────────────────────────────────────────
    alert_table = Table([[
        Paragraph(f'⚠  TRAFFIC VIOLATION NOTICE  ⚠  {severity.upper()} SEVERITY',
                  style(fontSize=10, textColor=colors.white,
                        alignment=TA_CENTER, fontName='Helvetica-Bold'))
    ]], colWidths=[180*mm])
    alert_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), sev_color),
        ('PADDING',    (0,0), (-1,-1), 8),
    ]))
    story.append(alert_table)
    story.append(Spacer(1, 5*mm))

    # ── CHALLAN META + AMOUNT BOX ────────────────────────────────────────────
    now      = datetime.now()
    due_date = now + timedelta(days=30)
    amount   = dict(violation_info)['amount']

    left_info = [
        ['Challan No:',      violation_id],
        ['Date & Time:',     now.strftime('%d %B %Y, %I:%M %p')],
        ['Due Date:',        due_date.strftime('%d %B %Y')],
        ['Section Violated:',dict(violation_info).get('section', 'MV Act')],
        ['Status:',          'PAID' if paid else 'UNPAID'],
    ]
    status_color = GREEN if paid else RED
    info_table = Table(left_info, colWidths=[45*mm, 75*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME',       (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTSIZE',       (0,0),(-1,-1), 9),
        ('TEXTCOLOR',      (0,0),(0,-1), BLUE),
        ('TEXTCOLOR',      (1,4),(1,4),  status_color),
        ('FONTNAME',       (1,4),(1,4),  'Helvetica-Bold'),
        ('BOTTOMPADDING',  (0,0),(-1,-1), 4),
        ('TOPPADDING',     (0,0),(-1,-1), 4),
    ]))

    amount_block = [
        [Paragraph('<font color="#DC2626"><b>FINE AMOUNT</b></font>',
                   style(fontSize=11, alignment=TA_CENTER))],
        [Paragraph(f'<font color="#0A1628"><b>₹ {amount:,}/-</b></font>',
                   style(fontSize=28, alignment=TA_CENTER, fontName='Helvetica-Bold'))],
        [Paragraph(f'<font color="#64748B">Indian Rupees {amount_in_words(amount)}</font>',
                   style(fontSize=7, alignment=TA_CENTER))],
    ]
    amount_table = Table(amount_block, colWidths=[55*mm])
    amount_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), LIGHT_GRAY),
        ('BOX',        (0,0),(-1,-1), 1.5, BLUE),
        ('PADDING',    (0,0),(-1,-1), 8),
        ('ALIGN',      (0,0),(-1,-1), 'CENTER'),
    ]))

    combined = Table([[info_table, amount_table]], colWidths=[125*mm, 60*mm])
    combined.setStyle(TableStyle([
        ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (0,0),(-1,-1), 0),
    ]))
    story.append(combined)
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 4*mm))

    # ── VEHICLE & OWNER ──────────────────────────────────────────────────────
    story.append(Paragraph('<b>VEHICLE &amp; OWNER INFORMATION</b>',
                           style(fontSize=10, textColor=BLUE, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 3*mm))

    vehicle_data = [
        ['Number Plate', plate_number,                    'Owner Name', owner_data.get('name','N/A')],
        ['Vehicle Type', owner_data.get('vehicle_type','N/A'), 'Email', owner_data.get('email','N/A')],
        ['Address',      owner_data.get('address','N/A'), 'Phone',      owner_data.get('phone','N/A')],
    ]
    v_table = Table(vehicle_data, colWidths=[35*mm, 55*mm, 30*mm, 65*mm])
    v_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,-1), LIGHT_GRAY),
        ('BACKGROUND', (2,0),(2,-1), LIGHT_GRAY),
        ('FONTNAME',   (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTNAME',   (2,0),(2,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),(-1,-1), 8.5),
        ('TEXTCOLOR',  (0,0),(0,-1), NAVY),
        ('TEXTCOLOR',  (2,0),(2,-1), NAVY),
        ('FONTNAME',   (1,0),(1,0),  'Helvetica-Bold'),
        ('TEXTCOLOR',  (1,0),(1,0),  RED),
        ('FONTSIZE',   (1,0),(1,0),  11),
        ('GRID',       (0,0),(-1,-1), 0.5, BORDER),
        ('PADDING',    (0,0),(-1,-1), 6),
    ]))
    story.append(v_table)
    story.append(Spacer(1, 5*mm))

    # ── VIOLATION DETAILS ────────────────────────────────────────────────────
    story.append(Paragraph('<b>VIOLATION DETAILS</b>',
                           style(fontSize=10, textColor=BLUE, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 3*mm))

    viol_data = [
        ['Violation Type', dict(violation_info)['name']],
        ['Description',    dict(violation_info).get('description','Traffic Rule Violated')],
        ['Legal Section',  dict(violation_info).get('section','Motor Vehicles Act')],
        ['Severity Level', severity],
        ['Fine Amount',    f'₹ {amount:,}/-'],
    ]
    viol_table = Table(viol_data, colWidths=[50*mm, 135*mm])
    viol_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,-1), colors.HexColor('#EFF6FF')),
        ('FONTNAME',   (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),(-1,-1), 9),
        ('TEXTCOLOR',  (0,0),(0,-1), BLUE),
        ('TEXTCOLOR',  (1,3),(1,3),  sev_color),
        ('FONTNAME',   (1,3),(1,3),  'Helvetica-Bold'),
        ('TEXTCOLOR',  (1,4),(1,4),  RED),
        ('FONTNAME',   (1,4),(1,4),  'Helvetica-Bold'),
        ('FONTSIZE',   (1,4),(1,4),  11),
        ('GRID',       (0,0),(-1,-1), 0.5, BORDER),
        ('PADDING',    (0,0),(-1,-1), 7),
    ]))
    story.append(viol_table)
    story.append(Spacer(1, 5*mm))

    # ── PAYMENT SECTION ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph('<b>PAYMENT INSTRUCTIONS</b>',
                           style(fontSize=10, textColor=BLUE, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 3*mm))

    payment_text = (
        f'Pay online at <b>echallan.parivahan.gov.in</b> or scan the QR code below.<br/>'
        f'Challan ID: <b>{violation_id}</b> | Amount: <b>₹{amount:,}/-</b> | '
        f'Due by: <b>{due_date.strftime("%d %B %Y")}</b><br/>'
        f'<font color="#DC2626"><b>Note: Late payment attracts ₹{int(amount*0.1)}/- penalty per week.</b></font>'
    )
    story.append(Paragraph(payment_text, style(fontSize=8.5, leading=14)))
    story.append(Spacer(1, 4*mm))

    # QR + Razorpay line
    try:
        qr_buf = get_qr(f"upi://pay?pa=traffic@upi&pn=TrafficFines&am={amount}&tn={violation_id}&cu=INR")
        qr_img = RLImage(qr_buf, width=30*mm, height=30*mm)
        razorpay_text = Paragraph(
            f'<b>Online Payment (Razorpay)</b><br/>'
            f'Visit: <font color="#1E3A8A">traffic-pay.example.com/pay/{violation_id}</font><br/>'
            f'or scan QR with any UPI app<br/>'
            f'<font color="#16A34A">Secure payment powered by Razorpay</font>',
            style(fontSize=8, leading=13))
        pay_table = Table([[qr_img, razorpay_text]], colWidths=[35*mm, 150*mm])
        pay_table.setStyle(TableStyle([
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('LEFTPADDING',  (0,0),(-1,-1), 5),
        ]))
        story.append(pay_table)
    except Exception as e:
        story.append(Paragraph(
            f'Pay online: traffic-pay.example.com/pay/{violation_id}',
            style(fontSize=9)))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        'This is a computer-generated e-Challan. For disputes contact your nearest RTO within 15 days.<br/>'
        'Appeal: traffic.court@gov.in | Helpline: 1800-XXX-XXXX | www.echallan.parivahan.gov.in',
        style(fontSize=7, textColor=MID_GRAY, alignment=TA_CENTER, leading=11)))

    doc.build(story)
    return pdf_path


def amount_in_words(n):
    ones = ['','One','Two','Three','Four','Five','Six','Seven','Eight','Nine',
            'Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen',
            'Seventeen','Eighteen','Nineteen']
    tens = ['','','Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety']
    if n == 0:      return 'Zero'
    if n < 20:      return ones[n]
    if n < 100:     return tens[n//10] + (' ' + ones[n%10] if n%10 else '')
    if n < 1000:    return ones[n//100] + ' Hundred' + (' ' + amount_in_words(n%100) if n%100 else '')
    if n < 100000:  return amount_in_words(n//1000) + ' Thousand' + (' ' + amount_in_words(n%1000) if n%1000 else '')
    return str(n)