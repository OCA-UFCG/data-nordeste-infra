import requests
from datetime import datetime
from config.settings import PROMETHEUS_URL, QUERY


def collect_requests():
    # Faz a requisição para a API do Prometheus
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": QUERY}
    )

    # Converte resposta para JSON
    data = response.json()

    # Pega o resultado da query
    result = data["data"]["result"]

    if not result:
        return None

    # Extrai timestamp e valor
    timestamp = float(result[0]["value"][0])
    total_requests = int(result[0]["value"][1])

    # Converte timestamp para data legível
    date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "date": date,
        "total_requests": total_requests,
        "raw_data": data
    }
