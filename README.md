# SalvadorTideBot

Python bot that sends a daily Telegram briefing for Salvador, BA with weather, sea conditions, wind and tide data.

## Features

- Fetches daily weather forecast for Salvador from CPTEC/INPE
- Fetches same-day sea and wind forecast from CPTEC/INPE wave endpoints
- Scrapes Salvador tide times from Tide-Forecast.com
- Sends one daily message to the Telegram chat configured in GitHub secrets
- Writes runtime logs to `logs/YYYY-MM-DD.log`

## Requirements

- Python 3.11+
- A Telegram bot token
- A Telegram chat ID

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Export the required environment variables:

```bash
export TELEGRAM_TOKEN="<your-bot-token>"
export TELEGRAM_CHAT_ID="<your-chat-id>"
```

## Local Usage

Run the bot manually with:

```bash
python main.py
```

The script fetches the current daily data and sends the Telegram message immediately.

## Data Sources

- Weather: `https://servicos.cptec.inpe.br/XML/cidade/7dias/242/previsao.xml`
- Waves and wind: `https://servicos.cptec.inpe.br/XML/cidade/242/dia/0/ondas.xml`
- Tides: `https://www.tide-forecast.com/locations/Salvador-Brazil/tides/latest`

## GitHub Actions

The workflow in `.github/workflows/actions.yml` runs every day at `09:00 UTC`, which corresponds to `06:00` in Salvador.

Required repository secrets:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

If the workflow fails, the generated files under `logs/` are uploaded as artifacts.

## Notes

- CPTEC responses are XML and can occasionally be unstable; the script fails with a non-zero exit code when upstream data cannot be fetched.
- Tide data currently comes from a public web page scrape because I could not validate a stable free Brazilian tide API without authentication.
