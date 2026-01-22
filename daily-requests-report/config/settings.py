import os

URLS = [
    {
        "name": "Requisições do DATANE Beta",
        "url": os.getenv("PROMETHEUS_URL")
    },
    {
        "name": "Requisições do DATANE AWS",
        "url": os.getenv("DATANE_AWS")
    }
]

QUERY = 'round(sum(increase(nginx_http_requests_total[1d])))'

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
