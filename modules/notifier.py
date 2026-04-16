import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your.email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'your_app_password')

def send_email_notification(to_email, owner_name, violation_id, violation_info, amount, pdf_path):
    try:
        viol     = dict(violation_info)
        due_date = (datetime.now() + timedelta(days=30)).strftime('%d %B %Y')

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"⚠️ Traffic Violation Notice - Challan #{violation_id}"
        msg['From']    = f"Traffic Enforcement System <{SMTP_USER}>"
        msg['To']      = to_email

        html_body = f"""<!DOCTYPE html>
<html>
<head><style>
  body{{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0;background:#f0f4f8;}}
  .container{{max-width:600px;margin:30px auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);}}
  .header{{background:linear-gradient(135deg,#0A1628,#1E3A8A);padding:30px;text-align:center;}}
  .header h1{{color:white;margin:0;font-size:22px;letter-spacing:1px;}}
  .header p{{color:#94A3B8;margin:5px 0 0;font-size:13px;}}
  .alert-bar{{background:#DC2626;color:white;text-align:center;padding:12px;font-weight:bold;font-size:14px;}}
  .body{{padding:30px;}}
  .amount-box{{background:linear-gradient(135deg,#FEF3C7,#FDE68A);border:2px solid #F59E0B;border-radius:10px;padding:20px;text-align:center;margin:20px 0;}}
  .amount-box .amount{{font-size:42px;font-weight:900;color:#DC2626;margin:5px 0;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin:20px 0;}}
  .info-item{{background:#F8FAFC;border-radius:8px;padding:14px;border-left:3px solid #1E3A8A;}}
  .info-item .key{{font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;}}
  .info-item .val{{font-size:14px;color:#0F172A;font-weight:600;margin-top:4px;}}
  .pay-btn{{display:block;background:linear-gradient(135deg,#1E3A8A,#3B82F6);color:white;text-align:center;padding:16px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold;margin:25px 0;}}
  .warning{{background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:15px;font-size:12px;color:#991B1B;}}
  .footer{{background:#F8FAFC;padding:20px;text-align:center;font-size:11px;color:#94A3B8;border-top:1px solid #E2E8F0;}}
</style></head>
<body>
<div class="container">
  <div class="header">
    <h1>🚦 e-CHALLAN NOTICE</h1>
    <p>Government of India | Ministry of Road Transport</p>
  </div>
  <div class="alert-bar">⚠️ TRAFFIC VIOLATION DETECTED — ACTION REQUIRED</div>
  <div class="body">
    <p style="font-size:16px;color:#1E293B;">Dear <strong>{owner_name}</strong>,</p>
    <p style="color:#475569;font-size:14px;">Your vehicle has been detected committing a traffic violation. Please pay the fine before the due date to avoid additional penalties.</p>
    <div class="amount-box">
      <div style="font-size:12px;color:#92400E;text-transform:uppercase;letter-spacing:1px;">Fine Amount Due</div>
      <div class="amount">₹{amount:,}/-</div>
      <div style="font-size:12px;color:#92400E;">Due by: <strong>{due_date}</strong></div>
    </div>
    <div class="info-grid">
      <div class="info-item"><div class="key">Challan ID</div><div class="val">{violation_id}</div></div>
      <div class="info-item"><div class="key">Violation</div><div class="val">{viol['name']}</div></div>
      <div class="info-item"><div class="key">Legal Section</div><div class="val">{viol.get('section','MV Act')}</div></div>
      <div class="info-item"><div class="key">Severity</div><div class="val">{viol.get('severity','Medium')}</div></div>
    </div>
    <a href="https://traffic-pay.example.com/pay/{violation_id}" class="pay-btn">
      💳 PAY NOW via Razorpay — ₹{amount:,}/-
    </a>
    <div class="warning">
      <strong>⚠️ Important:</strong> Failure to pay within 30 days may result in additional penalties. Fine PDF is attached.
    </div>
    <p style="font-size:12px;color:#64748B;margin-top:20px;">
      Disputes: <a href="mailto:traffic.court@gov.in">traffic.court@gov.in</a> | Helpline: 1800-XXX-XXXX
    </p>
  </div>
  <div class="footer">Automated notification from Smart Traffic Enforcement System. Do not reply.</div>
</div>
</body></html>"""

        msg.attach(MIMEText(html_body, 'html'))

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="challan_{violation_id}.pdf"')
                msg.attach(part)

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
        server.quit()
        return True

    except Exception as e:
        print(f"Email failed: {e}")
        return False

def send_sms_notification(phone, owner_name, violation_id, violation_name, amount):
    # Replace with MSG91 / Twilio / Fast2SMS in production
    msg = f"Traffic Challan! Dear {owner_name}, violation: {violation_name}. Challan: {violation_id}. Fine: Rs.{amount}. Pay at echallan.parivahan.gov.in"
    print(f"[SMS DEMO] To:{phone} | {msg}")
    return True