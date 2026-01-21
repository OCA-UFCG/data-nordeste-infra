# Daily Requests Report

This project collects daily HTTP request metrics from **Prometheus** (using NGINX metrics as an example)
and sends a summary report by **email**.

It is designed to run manually or automatically using **cron**
on a VM or server.

---

## What this project does

1. Queries Prometheus for the total number of HTTP requests in the last 24 hours
2. Formats the collected data
3. Sends the information by email to one or more recipients

---

## Project structure

```text
daily-requests-report/
├── app/
│   ├── __init__.py
│   ├── prometheus_collector.py   # Collects data from Prometheus
│   └── email_sender.py           # Sends email with the report
│
├── config/
│   ├── __init__.py
│   └── settings.py               # Loads environment variables
│
├── scripts/
│   ├── run.py                    # Main entry point
│   └── run.sh                    # Shell script used by cron
│
├── .env.exemple                          # Environment variables
├── requirements.txt
└── README.md
