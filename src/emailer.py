import os
import smtplib
from email.message import EmailMessage
from typing import Optional

class EmailConfigError(RuntimeError):
    pass


def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user)
    if not user or not password or not from_addr:
        raise EmailConfigError(
            "Config SMTP incompleta. Define SMTP_USER, SMTP_PASS y opcionalmente SMTP_FROM en .env"
        )
    return host, port, user, password, from_addr


def send_email_smtp(to: str, subject: str, html_body: str, text_body: Optional[str] = None):
    host, port, user, password, from_addr = _get_smtp_config()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    if not text_body:
        text_body = "Reporte de precios adjunto en formato HTML."

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
