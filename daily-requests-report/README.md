# Daily Requests Report

This project collects daily HTTP request metrics from **Prometheus** (using NGINX metrics as an example)
and sends a summary report by **email**.

It is designed to be simple, modular, and easy to run manually or automatically using **cron**
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
├── .env.example                  # Environment variables 
├── requirements.txt
└── README.md
````

---
# Configure your .env
``` 
cp .env.example .env
# Populate values
source .env
```
---
## Configure the path to the project's directory in the run.sh
``` 
PROJECT_DIR="/path-to-daily-requests-report/" 
```

## Requirements

* Python 3.8 or higher
* Access to a running Prometheus instance
* SMTP credentials for sending emails

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment variables

Create a `.env` file in the project root:

```env
PROMETHEUS_URL=http://localhost:****

EMAIL_FROM=your_email@gmail.com
EMAIL_TO=email1@example.com,email2@example.com
EMAIL_PASSWORD=*********
```

* `EMAIL_TO` supports **multiple recipients**, separated by commas
* `PROMETHEUS_URL` must include `http://` or `https://`

---

## How to run manually

From the project root:

```bash
export $(grep -v '^#' .env | xargs)
python -m scripts.run
```

If everything is configured correctly, the script will:

* Query Prometheus
* Print the results
* Send the email report

---

## Running automatically with cron

### Make the script executable

```bash
chmod +x absolute-path-to/run.sh
```

### Edit the crontab

```bash
crontab -e
```

### Example cron job (runs every day at 23:59)

```bash
59 23 * * * /home/your-user/daily-requests-report/scripts/run.sh
```

Using `run.sh` ensures that environment variables are loaded correctly when running from cron.

---


