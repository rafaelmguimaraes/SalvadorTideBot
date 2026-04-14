"""Send a daily Salvador weather, sea and tide briefing to Telegram."""

from datetime import date, datetime, timezone
from enum import IntEnum
import logging
import os
import re
import sys
from xml.etree import ElementTree

from parsel import Selector
import requests
from zoneinfo import ZoneInfo

CPTEC_CITY_ID = 242
SALVADOR_TIMEZONE = ZoneInfo("America/Bahia")
CPTEC_WEATHER_URL = (
    f"https://servicos.cptec.inpe.br/XML/cidade/7dias/{CPTEC_CITY_ID}/previsao.xml"
)
CPTEC_WAVES_DAY_URL = (
    f"https://servicos.cptec.inpe.br/XML/cidade/{CPTEC_CITY_ID}/dia/0/ondas.xml"
)
CPTEC_WAVES_ALL_URL = (
    f"https://servicos.cptec.inpe.br/XML/cidade/{CPTEC_CITY_ID}/todos/tempos/ondas.xml"
)
TIDE_FORECAST_URL = (
    "https://www.tide-forecast.com/locations/Salvador-Brazil/tides/latest"
)
TIMEOUT = 20
LOG_DIR = "logs"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}
WEATHER_CODE_DESCRIPTIONS = {
    "ec": "Encoberto com chuvas isoladas",
    "ci": "Chuvas isoladas",
    "c": "Chuva",
    "in": "Instavel",
    "pp": "Possibilidade de pancadas de chuva",
    "cm": "Chuva pela manha",
    "cn": "Chuva a noite",
    "pt": "Pancadas de chuva a tarde",
    "pm": "Pancadas de chuva pela manha",
    "np": "Nublado com pancadas de chuva",
    "pc": "Pancadas de chuva",
    "pn": "Parcialmente nublado",
    "cv": "Chuvisco",
    "ch": "Chuvoso",
    "t": "Tempestade",
    "ps": "Predominio de sol",
    "e": "Encoberto",
    "n": "Nublado",
    "cl": "Ceu claro",
    "nv": "Nevoeiro",
    "g": "Geada",
    "ne": "Neve",
    "nd": "Nao definido",
    "pnt": "Pancadas de chuva a noite",
    "psc": "Possibilidade de chuva",
    "pcm": "Possibilidade de chuva pela manha",
    "pct": "Possibilidade de chuva a tarde",
    "pcn": "Possibilidade de chuva a noite",
    "npt": "Nublado com pancadas a tarde",
    "npm": "Nublado com pancadas pela manha",
    "npn": "Nublado com pancadas a noite",
    "ncn": "Nublado com possibilidade de chuva a noite",
    "nct": "Nublado com possibilidade de chuva a tarde",
    "ncm": "Nublado com possibilidade de chuva pela manha",
    "npp": "Nublado com pancadas e trovoadas",
    "vn": "Variacao de nuvens",
    "ct": "Chuva a tarde",
    "ppn": "Possibilidade de pancadas a noite",
    "ppm": "Possibilidade de pancadas pela manha",
}
WAVE_PERIOD_LABELS = {
    "manha": "Manha",
    "tarde": "Tarde",
    "noite": "Noite",
}
TIDE_KIND_LABELS = {
    "High Tide": "Alta",
    "Low Tide": "Baixa",
}
SUN_TIMES_PATTERN = re.compile(
    r"Sunrise is at\s+(?P<sunrise>[0-9:]+[ap]m)\s+and sunset is at\s+"
    r"(?P<sunset>[0-9:]+[ap]m)",
    re.IGNORECASE,
)


class ErrorCode(IntEnum):
    SUCCESS = 0
    TOKEN_NOT_AVAILABLE = 2
    FETCH_FAILED = 3
    DATA_NOT_FOUND = 4
    TELEGRAM_FAILED = 5


class TokenNotAvailableException(Exception):
    """Raised when Telegram credentials are missing."""


class FetchDataException(Exception):
    """Raised when one of the upstream sources fails."""


class DataNotFoundException(Exception):
    """Raised when upstream data cannot be parsed into a usable payload."""


class TelegramNotificationException(Exception):
    """Raised when Telegram rejects the outgoing message."""


def configure_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{date.today().isoformat()}.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)


def build_http_session():
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


def load_tokens():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise TokenNotAvailableException(
            "TELEGRAM_TOKEN or TELEGRAM_CHAT_ID is not configured."
        )
    return token, chat_id


def clean_text(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def format_number(value):
    formatted = f"{value:.1f}".rstrip("0").rstrip(".")
    return formatted.replace(".", ",")


def format_date_br(value):
    return value.strftime("%d/%m/%Y")


def format_time_br(value):
    return value.strftime("%H:%M")


def parse_cptec_daily_date(raw_value):
    return datetime.strptime(clean_text(raw_value), "%Y-%m-%d").date()


def parse_cptec_wave_datetime(raw_value):
    parsed = datetime.strptime(clean_text(raw_value), "%d-%m-%Y %Hh Z")
    return parsed.replace(tzinfo=timezone.utc).astimezone(SALVADOR_TIMEZONE)


def parse_clock(raw_value):
    normalized = clean_text(raw_value).upper()
    normalized = re.sub(r"(?<=\d)(AM|PM)$", r" \1", normalized)
    if normalized.startswith("00:"):
        normalized = f"12:{normalized[3:]}"
    return datetime.strptime(normalized, "%I:%M %p").time()


def fetch_xml_root(session, url, source_name):
    try:
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchDataException(f"Error fetching {source_name}: {exc}") from exc

    try:
        return ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise FetchDataException(
            f"Invalid XML returned by {source_name}: {exc}"
        ) from exc


def describe_weather(code):
    normalized_code = clean_text(code).lower()
    if not normalized_code:
        return "Condicao indisponivel"
    return WEATHER_CODE_DESCRIPTIONS.get(
        normalized_code,
        f"Codigo {normalized_code.upper()}",
    )


def fetch_weather(session):
    root = fetch_xml_root(session, CPTEC_WEATHER_URL, "CPTEC weather forecast")
    city_name = clean_text(root.findtext("nome")) or "Salvador"
    state = clean_text(root.findtext("uf")) or "BA"
    updated_at = clean_text(root.findtext("atualizacao"))
    forecasts = []

    for forecast_node in root.findall("previsao"):
        forecast_date_raw = clean_text(forecast_node.findtext("dia"))
        if not forecast_date_raw:
            continue
        forecasts.append(
            {
                "date": parse_cptec_daily_date(forecast_date_raw),
                "code": clean_text(forecast_node.findtext("tempo")).lower(),
                "description": describe_weather(forecast_node.findtext("tempo")),
                "maximum": int(clean_text(forecast_node.findtext("maxima")) or 0),
                "minimum": int(clean_text(forecast_node.findtext("minima")) or 0),
                "uv_index": clean_text(forecast_node.findtext("iuv")) or "n/d",
            }
        )

    if not forecasts:
        raise DataNotFoundException(
            "CPTEC weather forecast returned no usable entries."
        )

    today = datetime.now(SALVADOR_TIMEZONE).date()
    today_forecast = next(
        (forecast for forecast in forecasts if forecast["date"] == today),
        forecasts[0],
    )

    return {
        "city_name": city_name,
        "state": state,
        "updated_at": updated_at,
        "today": today_forecast,
        "tomorrow": forecasts[1] if len(forecasts) > 1 else None,
    }


def parse_wave_period(period_name, period_node):
    forecast_at = parse_cptec_wave_datetime(period_node.findtext("dia"))
    height = float(clean_text(period_node.findtext("altura")) or 0)
    wind_speed = float(clean_text(period_node.findtext("vento")) or 0)
    return {
        "label": WAVE_PERIOD_LABELS.get(period_name, period_name.title()),
        "forecast_at": forecast_at,
        "agitation": clean_text(period_node.findtext("agitacao")) or "n/d",
        "height": height,
        "direction": clean_text(period_node.findtext("direcao")) or "n/d",
        "wind_speed": wind_speed,
        "wind_direction": clean_text(period_node.findtext("vento_dir")) or "n/d",
    }


def fetch_waves_from_daily_endpoint(session):
    root = fetch_xml_root(session, CPTEC_WAVES_DAY_URL, "CPTEC daily waves forecast")
    periods = []
    for period_name in ("manha", "tarde", "noite"):
        period_node = root.find(period_name)
        if period_node is None:
            continue
        periods.append(parse_wave_period(period_name, period_node))

    if not periods:
        raise DataNotFoundException(
            "CPTEC daily waves forecast returned no usable periods."
        )

    return {
        "updated_at": clean_text(root.findtext("atualizacao")),
        "periods": periods,
    }


def fetch_waves_from_full_endpoint(session):
    root = fetch_xml_root(session, CPTEC_WAVES_ALL_URL, "CPTEC full waves forecast")
    target_date = datetime.now(SALVADOR_TIMEZONE).date()
    selected_nodes = []

    for forecast_node in root.findall("previsao"):
        forecast_at = parse_cptec_wave_datetime(forecast_node.findtext("dia"))
        if forecast_at.date() == target_date:
            selected_nodes.append((forecast_at, forecast_node))

    if not selected_nodes:
        raise DataNotFoundException(
            "CPTEC full waves forecast returned no data for today."
        )

    selected_nodes.sort(key=lambda item: item[0])
    periods = []
    fallback_labels = ("Manha", "Tarde", "Noite")
    for index, (_, forecast_node) in enumerate(selected_nodes[:3]):
        periods.append(
            {
                **parse_wave_period(fallback_labels[index].lower(), forecast_node),
                "label": fallback_labels[index],
            }
        )

    return {
        "updated_at": clean_text(root.findtext("atualizacao")),
        "periods": periods,
    }


def fetch_waves(session):
    errors = []
    for fetcher in (fetch_waves_from_daily_endpoint, fetch_waves_from_full_endpoint):
        try:
            return fetcher(session)
        except (FetchDataException, DataNotFoundException) as exc:
            errors.append(str(exc))

    raise FetchDataException(" | ".join(errors))


def parse_tide_events(table_selector, reference_date):
    events = []
    for row in table_selector.css("tr")[1:]:
        cells = row.css("td")
        if len(cells) < 3:
            continue

        tide_kind = clean_text(" ".join(cells[0].css("::text").getall()))
        raw_time = clean_text(" ".join(cells[1].css("b::text").getall()))
        raw_height = clean_text(" ".join(cells[2].css("b::text").getall()))
        if not tide_kind or not raw_time or not raw_height:
            continue

        clock_time = parse_clock(raw_time)
        events.append(
            {
                "kind": tide_kind,
                "label": TIDE_KIND_LABELS.get(tide_kind, tide_kind),
                "time": clock_time,
                "datetime": datetime.combine(
                    reference_date, clock_time, SALVADOR_TIMEZONE
                ),
                "height": raw_height,
            }
        )

    if not events:
        raise DataNotFoundException("Tide page returned no usable tide events.")

    events.sort(key=lambda event: event["datetime"])
    return events


def fetch_tides(session):
    try:
        response = session.get(TIDE_FORECAST_URL, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchDataException(f"Error fetching Tide-Forecast page: {exc}") from exc

    selector = Selector(text=response.text)
    summary = clean_text(" ".join(selector.css("p.tide-header-summary::text").getall()))
    datum = clean_text(
        " ".join(selector.css("div.tide-header-today__datum-source ::text").getall())
    )
    table_selector = selector.css("table.tide-day-tides").getall()
    if not table_selector:
        raise DataNotFoundException(
            "Tide-Forecast page did not contain the daily tide table."
        )

    today = datetime.now(SALVADOR_TIMEZONE).date()
    events = parse_tide_events(selector.css("table.tide-day-tides")[0], today)

    sunrise = None
    sunset = None
    sun_times_match = SUN_TIMES_PATTERN.search(summary)
    if sun_times_match:
        sunrise = parse_clock(sun_times_match.group("sunrise"))
        sunset = parse_clock(sun_times_match.group("sunset"))

    now_local = datetime.now(SALVADOR_TIMEZONE)
    upcoming_event = next(
        (event for event in events if event["datetime"] >= now_local),
        None,
    )

    return {
        "summary": summary,
        "datum": datum.replace("Tide Datum:", "").strip(),
        "events": events,
        "sunrise": sunrise,
        "sunset": sunset,
        "upcoming_event": upcoming_event,
    }


def build_weather_lines(weather_payload):
    today_forecast = weather_payload["today"]
    lines = [
        "Clima",
        f"- Condicao: {today_forecast['description']}",
        f"- Temperatura: {today_forecast['minimum']}C a {today_forecast['maximum']}C",
        f"- UV: {today_forecast['uv_index']}",
    ]

    tomorrow_forecast = weather_payload.get("tomorrow")
    if tomorrow_forecast:
        lines.append(
            "- Amanha: "
            f"{tomorrow_forecast['description']}, "
            f"{tomorrow_forecast['minimum']}C a {tomorrow_forecast['maximum']}C"
        )

    return lines


def build_wave_lines(wave_payload):
    heights = [period["height"] for period in wave_payload["periods"]]
    wind_speeds = [period["wind_speed"] for period in wave_payload["periods"]]
    lines = [
        "Mar e vento",
        "- Resumo: ondas de "
        f"{format_number(min(heights))} a {format_number(max(heights))} m; "
        f"vento CPTEC entre {format_number(min(wind_speeds))} e {format_number(max(wind_speeds))}",
    ]

    for period in wave_payload["periods"]:
        lines.append(
            f"- {period['label']}: "
            f"{format_time_br(period['forecast_at'])}, "
            f"{period['agitation']}, "
            f"ondas {format_number(period['height'])} m {period['direction']}, "
            f"vento {period['wind_direction']} {format_number(period['wind_speed'])}"
        )

    return lines


def build_tide_lines(tide_payload):
    lines = ["Mare"]
    if tide_payload["upcoming_event"]:
        next_event = tide_payload["upcoming_event"]
        lines.append(
            f"- Proxima {next_event['label'].lower()}: "
            f"{format_time_br(next_event['datetime'])} ({next_event['height']})"
        )

    for event in tide_payload["events"]:
        lines.append(
            f"- {event['label']}: {format_time_br(event['datetime'])} ({event['height']})"
        )

    if tide_payload["sunrise"] and tide_payload["sunset"]:
        lines.append(
            f"- Sol: {format_time_br(datetime.combine(date.today(), tide_payload['sunrise']))} / "
            f"{format_time_br(datetime.combine(date.today(), tide_payload['sunset']))}"
        )

    if tide_payload["datum"]:
        lines.append(f"- Datum: {tide_payload['datum']}")

    return lines


def build_telegram_message(weather_payload, wave_payload, tide_payload):
    today = datetime.now(SALVADOR_TIMEZONE).date()
    lines = [
        f"Bom dia! Boletim de Salvador ({format_date_br(today)})",
        "",
        *build_weather_lines(weather_payload),
        "",
        *build_wave_lines(wave_payload),
        "",
        *build_tide_lines(tide_payload),
        "",
        "Fontes",
        f"- CPTEC/INPE (atualizacao do clima: {weather_payload['updated_at']})",
        f"- CPTEC/INPE (ondas: {wave_payload['updated_at']})",
        "- Tide-Forecast.com",
    ]
    return "\n".join(lines)


def notify_by_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, data=payload, timeout=TIMEOUT)
        response.raise_for_status()
        response_json = response.json()
    except requests.RequestException as exc:
        raise TelegramNotificationException(
            f"Error contacting Telegram API: {exc}"
        ) from exc

    if not response_json.get("ok"):
        description = response_json.get("description", "unknown Telegram error")
        raise TelegramNotificationException(
            f"Telegram API returned an error: {description}"
        )


def main():
    configure_logging()
    logger = logging.getLogger(__name__)

    try:
        telegram_token, telegram_chat_id = load_tokens()
        session = build_http_session()
        weather_payload = fetch_weather(session)
        wave_payload = fetch_waves(session)
        tide_payload = fetch_tides(session)
        message = build_telegram_message(weather_payload, wave_payload, tide_payload)

        logger.info(
            "Prepared daily briefing for %s/%s.",
            weather_payload["city_name"],
            weather_payload["state"],
        )
        notify_by_telegram(telegram_token, telegram_chat_id, message)
        logger.info("Daily briefing sent successfully.")
        return ErrorCode.SUCCESS
    except TokenNotAvailableException as exc:
        logger.error(str(exc))
        return ErrorCode.TOKEN_NOT_AVAILABLE
    except FetchDataException as exc:
        logger.error(str(exc))
        return ErrorCode.FETCH_FAILED
    except DataNotFoundException as exc:
        logger.error(str(exc))
        return ErrorCode.DATA_NOT_FOUND
    except TelegramNotificationException as exc:
        logger.error(str(exc))
        return ErrorCode.TELEGRAM_FAILED
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return ErrorCode.FETCH_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
