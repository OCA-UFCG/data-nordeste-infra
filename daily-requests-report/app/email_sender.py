import smtplib
from email.message import EmailMessage
from config.settings import EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD


def send_email(reports):
    msg = EmailMessage()


    msg["Subject"] = f"Relatório Diário de Requisições"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)

    body_lines = []
    body_lines.append("RELATÓRIO DIÁRIO DE REQUISIÇÕES\n")

    for r in reports:
        title = f"{r['name']} ({r['url']})"

        if r.get("error"):
            body_lines.append(title)
            body_lines.append(f"❌ Erro: {r['error']}")
        else:
            body_lines.append(title)
            body_lines.append(f"Data: {r['date']}")
            body_lines.append(f"Total de requisições: {r['total_requests']}")

        body_lines.append("-" * 50)


    msg.set_content("\n".join(body_lines))

    # 📤 Envio do email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
