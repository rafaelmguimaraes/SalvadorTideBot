# SalvadorTideBot

Python bot that sends a daily Telegram briefing for Salvador, BA with weather, sea conditions, wind, tide and moon data.

## What It Sends

Every day at `06:00` in Salvador, the bot sends a message like this:

```text
Bom dia! Boletim de Salvador - 14/04/2026

CLIMA
- Condicao: Chuva
- Temperatura: 24C a 29C
- Amanha: Chuva, 24C a 29C

MAR E VENTO
- Resumo: ondas de 1,5 m a 1,6 m; vento entre 12,1 nos (22,3 km/h) e 13,2 nos (24,5 km/h)
- Manha: 09:00, Fraco, ondas 1,6 m de ESE, vento SSE 12,2 nos (22,7 km/h)
- Tarde: 15:00, Fraco, ondas 1,5 m de ESE, vento SE 12,1 nos (22,3 km/h)
- Noite: 18:00, Fraco, ondas 1,5 m de ESE, vento SE 13,2 nos (24,5 km/h)

MARE
- Alta: 01:32 (2,06 m)
- Baixa: 07:32 (0,41 m)
- Alta: 13:53 (2,27 m)
- Baixa: 20:00 (0,35 m)

SOL E LUA
- Sol: nascer 05:39 / por 17:28
- Lua: fase Minguante / nascer 03:42 / por 16:01
```

## Features

- Fetches daily weather forecast for Salvador from CPTEC/INPE
- Fetches same-day sea and wind forecast from CPTEC/INPE wave endpoints
- Scrapes Salvador tide times from Tide-Forecast.com
- Fetches moon phase, moonrise and moonset from MET Norway
- Sends one daily message to the Telegram chat configured in GitHub secrets
- Writes runtime logs to `logs/YYYY-MM-DD.log`

## Requirements

- Python 3.11+
- A Telegram bot token
- A Telegram chat ID

## Fork And Setup

If you want to use this bot in your own GitHub account:

1. Fork this repository.
2. In your fork, open `Settings` > `Secrets and variables` > `Actions`.
3. Create your Telegram bot and get the credentials.
4. Add the required repository secrets.
5. Run the workflow manually once to validate everything.

## Create The Telegram Bot

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather).
2. Send `/newbot`.
3. Choose a display name for your bot.
4. Choose a unique username ending with `bot`.
5. Copy the token returned by BotFather.

This token is the value you must save as `TELEGRAM_TOKEN` in your repository secrets.

## Get Your Telegram Chat ID

You need the chat ID where the bot will post the daily message.

1. Start a conversation with your bot, or add it to a group/channel where you want the messages.
2. Send any message to the bot or group.
3. Open this URL in the browser, replacing `<TOKEN>` with your bot token:

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

4. Look for `chat` and copy the `id` value.

Examples:

- Private chat IDs are usually positive numbers
- Group chat IDs are usually negative numbers

Save that value as `TELEGRAM_CHAT_ID` in your repository secrets.

## Configure GitHub Secrets

Add these secrets in your forked repository under `Settings` > `Secrets and variables` > `Actions`:

- `TELEGRAM_TOKEN`: token created with BotFather
- `TELEGRAM_CHAT_ID`: chat ID that will receive the daily message

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

To validate your fork after adding the secrets:

1. Open the `Actions` tab in GitHub.
2. Select the `run main.py` workflow.
3. Click `Run workflow`.
4. Confirm that the run finishes successfully and that the Telegram message is delivered.

If the workflow fails, the generated files under `logs/` are uploaded as artifacts.

## Notes

- CPTEC responses are XML and can occasionally be unstable; when weather or wave data is unavailable, the bot sends the briefing with those sections marked as temporarily unavailable.
- Tide data currently comes from a public web page scrape because I could not validate a stable free Brazilian tide API without authentication.
