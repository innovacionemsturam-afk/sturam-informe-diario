"""Envío de correo HTML por Gmail (SMTP SSL con App Password).

Pensado para ejecutarse de forma autónoma en la nube (GitHub Actions / Cloud Run)
sin depender de una sesión interactiva local, devolviendo el Message-ID real.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
import os
import smtplib


def send_html_email(
    subject: str,
    plain_text: str,
    html_body: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
) -> str:
    """Envía un único correo multipart/alternative (sin adjuntos) y devuelve el Message-ID."""
    sender = os.environ.get("GMAIL_SENDER", "innovacion.emsturam@gmail.com")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        raise RuntimeError(
            "Falta GMAIL_APP_PASSWORD en variables de entorno para envío autónomo en la nube."
        )

    cc_list = cc_addrs or []

    msg = MIMEMultipart("alternative")
    msg_id = make_msgid(domain="emsturam.com.ar")
    msg["Message-ID"] = msg_id
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    all_recipients = list(dict.fromkeys(to_addrs + cc_list))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(sender, app_password)
        server.sendmail(sender, all_recipients, msg.as_string())

    return msg_id
