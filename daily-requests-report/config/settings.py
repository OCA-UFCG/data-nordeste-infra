import os

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL")

QUERY = 'round(sum(increase(nginx_http_requests_total[1d])))'

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
