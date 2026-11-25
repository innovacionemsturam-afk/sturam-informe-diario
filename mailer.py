"""Envío de correo HTML por Gmail (SMTP SSL con App Password).

Mantiene el informe completo visible en el cuerpo del correo (con el logo
embebido por Content-ID) y, adicionalmente, adjunta el archivo .html autónomo
(con el logo incrustado en Base64) listo para descargar y compartir.
"""

import base64
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from pathlib import Path
import os
import smtplib


def build_standalone_html(html_body: str, logo_path: Path | None) -> str:
    """Reemplaza cid:sturam_logo por un data URI Base64 para el archivo .html descargable."""
    if not logo_path or not logo_path.exists():
        return html_body
    b64_logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    data_uri = f"data:image/png;base64,{b64_logo}"
    return html_body.replace("cid:sturam_logo", data_uri)


def send_html_email(
    subject: str,
    plain_text: str,
    html_body: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    logo_path: Path | None = None,
    attach_html_filename: str | None = None,
) -> str:
    """Envía el correo con cuerpo HTML + CID y adjunta el archivo .html compartible."""
    sender = os.environ.get("GMAIL_SENDER", "innovacion.emsturam@gmail.com")
    app_password = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not app_password:
        raise RuntimeError(
            "Falta GMAIL_APP_PASSWORD en variables de entorno para envío autónomo en la nube."
        )

    cc_list = cc_addrs or []

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))

    if logo_path and logo_path.exists():
        related_part = MIMEMultipart("related")
        related_part.attach(alt_part)
        img = MIMEImage(logo_path.read_bytes())
        img.add_header("Content-ID", "<sturam_logo>")
        img.add_header("Content-Disposition", "inline", filename=logo_path.name)
        related_part.attach(img)
    else:
        related_part = alt_part

    # Contenedor mixed para incluir el cuerpo visual + el archivo .html adjunto
    msg = MIMEMultipart("mixed")
    msg.attach(related_part)

    fname = attach_html_filename or "Informe_Estrategico_STURAM.html"
    standalone_html = build_standalone_html(html_body, logo_path)
    html_attachment = MIMEApplication(
        standalone_html.encode("utf-8"), _subtype="html"
    )
    html_attachment.add_header(
        "Content-Disposition", "attachment", filename=fname
    )
    msg.attach(html_attachment)

    msg_id = make_msgid(domain="emsturam.com.ar")
    msg["Message-ID"] = msg_id
    msg["From"] = sender
    msg["To"] = ", ".join(to_addrs)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject

    all_recipients = list(dict.fromkeys(to_addrs + cc_list))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(sender, app_password)
        server.sendmail(sender, all_recipients, msg.as_string())

    return msg_id
