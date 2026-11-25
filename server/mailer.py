"""Sending sign-up codes.

Email: set these environment variables (e.g. a Gmail account with an "app password") and codes are emailed:
  SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_USER=you@gmail.com  SMTP_PASSWORD=<app password>
Without them the server runs in TEST MODE: the code is printed in the server window and shown on the page.
SMS (phone sign-up) costs money per message (e.g. Twilio), so phone codes are always test mode for now.
"""

import os
import smtplib
from email.message import EmailMessage


def email_configured():
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))


def send_code(contact, contact_type, code, purpose="signup"):
    """Returns True if really sent; False = test mode (show the code on the page)."""
    if contact_type == "email" and email_configured():
        msg = EmailMessage()
        msg["Subject"] = f"Your Speakoff code: {code}" if purpose == "signup" else f"Reset your Speakoff password: {code}"
        msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
        msg["To"] = contact
        what = "sign-up code" if purpose == "signup" else "code to reset your password"
        msg.set_content(f"Your Speakoff {what} is {code}.\nIt is valid for 10 minutes.\n\n"
                        f"If you did not ask for it, you can ignore this email.")
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587)), timeout=20) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
        return True
    print(f"[TEST MODE] {purpose} code for {contact}: {code}", flush=True)
    return False
