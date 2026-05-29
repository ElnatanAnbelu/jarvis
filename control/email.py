import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import json
import os

def load_config():
    env = Path(__file__).parent.parent / ".env"
    cfg = {}
    for line in env.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg

def send_email(to: str, subject: str, body: str) -> str:
    cfg = load_config()
    gmail_user = cfg.get('GMAIL_USER')
    gmail_pass = cfg.get('GMAIL_APP_PASSWORD')
    if not gmail_user or not gmail_pass:
        return "Gmail not configured. Add GMAIL_USER and GMAIL_APP_PASSWORD to .env"
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
        return f"Email sent to {to}."
    except Exception as e:
        return f"Failed to send email: {e}"

def read_emails(count: int = 5, primary_only: bool = True,
                gmail_user: str = None, gmail_pass: str = None) -> str:
    cfg = load_config()
    gmail_user = gmail_user or cfg.get('GMAIL_USER')
    gmail_pass = gmail_pass or cfg.get('GMAIL_APP_PASSWORD')
    if not gmail_user or not gmail_pass:
        return "Gmail not configured."
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(gmail_user, gmail_pass)
        mail.select('inbox')
        # Gmail-specific extension: limit to the Primary tab when requested.
        # X-GM-RAW takes Gmail search syntax — "category:primary" mirrors the
        # Primary tab in the web UI. Falls back gracefully if unsupported.
        if primary_only:
            try:
                _, msgs = mail.search(None, 'X-GM-RAW', '"category:primary is:unread"')
            except Exception:
                _, msgs = mail.search(None, 'UNSEEN')
        else:
            _, msgs = mail.search(None, 'UNSEEN')
        ids = msgs[0].split()[-count:]
        results = []
        for uid in reversed(ids):
            _, data = mail.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(data[0][1])
            subject = msg.get('Subject', '(no subject)')
            sender = msg.get('From', 'Unknown')
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')[:300]
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')[:300]
            results.append(f"FROM: {sender}\nSUBJECT: {subject}\n{body.strip()}")
        mail.logout()
        return '\n\n---\n\n'.join(results) if results else "No unread emails."
    except Exception as e:
        return f"Could not read emails: {e}"
