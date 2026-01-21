import json
from app.prometheus_collector import collect_requests
from app.email_sender import send_email


def main():
    data = collect_requests()

    if not data:
        print("Nenhum dado encontrado.")
        return

    print("Data:", data["date"])
    print("Total de requisições:", data["total_requests"])

    # Salva o retorno completo em JSON
    with open("total_requests.json", "w") as file:
        json.dump(data["raw_data"], file, indent=2)

    send_email(data)
    print("E-mail enviado com sucesso.")


if __name__ == "__main__":
    main()
