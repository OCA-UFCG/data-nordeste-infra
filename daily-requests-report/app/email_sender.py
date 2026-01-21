import smtplib
from email.message import EmailMessage
from config.settings import EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD


def send_email(data):
    msg = EmailMessage()
    msg["Subject"] = "TESTE: Relatório de Requisições"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)

    msg.set_content(
        f"Data: {data['date']}\n"
        f"Total de requisições: {data['total_requests']}"
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
