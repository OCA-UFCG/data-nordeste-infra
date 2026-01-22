import requests
from datetime import datetime
from config.settings import URLS, QUERY


def collect_requests():
    reports = []

    for target in URLS:
        name = target["name"]
        url = target["url"]

        try:
            response = requests.get(
                f"{url}/api/v1/query",
                params={"query": QUERY},
                timeout=10
            )

            data = response.json()
            result = data["data"]["result"]

            if not result:
                reports.append({
                    "name": name,
                    "url": url,
                    "error": "Sem resultados",
                    "date": None,
                    "total_requests": 0,
                    "raw_data": data
                })
                continue

            timestamp = float(result[0]["value"][0])
            total_requests = int(result[0]["value"][1])
            date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

            reports.append({
                "name": name,
                "url": url,
                "date": date,
                "total_requests": total_requests,
                "raw_data": data
            })

        except Exception as e:
            reports.append({
                "name": name,
                "url": url,
                "error": str(e),
                "date": None,
                "total_requests": 0,
                "raw_data": None
            })

    return reports
