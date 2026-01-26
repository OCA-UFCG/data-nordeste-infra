import json
from app.prometheus_collector import collect_requests
from app.email_sender import send_email


def main():
    reports = collect_requests()

    if not reports:
        print("Nenhum dado encontrado.")
        return

    print("\n RELATÓRIO DE REQUISIÇÕES\n")

    for r in reports:
        header = f"{r['name']} ({r['url']})"
        print(header)

        if r.get("error"):
            print(f"Erro: {r['error']}")
        else:
            print("Data:", r["date"])
            print("Total de requisições:", r["total_requests"])

        print("-" * 50)

    # Salva relatório completo
    with open("total_requests.json", "w") as file:
        json.dump(reports, file, indent=2, ensure_ascii=False)

    send_email(reports)

    print("\n E-mail enviado com sucesso.\n")

if __name__ == "__main__":
    main()
