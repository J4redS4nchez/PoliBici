# mailer.py
import smtplib
from email.message import EmailMessage


def send_mail_smtp(server: str, port: int, user: str, password: str,
                   sender: str, to: str, subject: str, html: str, text: str | None = None):
    """
    Envía un correo simple por SMTP (Office 365/Outlook: smtp.office365.com:587 + STARTTLS).
    - 'sender' puede ser 'Nombre <correo@dominio>' o solo 'correo@dominio'.
    """
    msg = EmailMessage()
    msg["From"] = sender or user
    msg["To"] = to
    msg["Subject"] = subject

    if text:
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(html, subtype="html")

    # Conexión y envío
    with smtplib.SMTP(server, port) as smtp:
        smtp.set_debuglevel(0)       # pon 1 si quieres ver el diálogo SMTP en consola
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, password)   # requiere SMTP AUTH habilitado / app password si hay MFA
        smtp.send_message(msg)
