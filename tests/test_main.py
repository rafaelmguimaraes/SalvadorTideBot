from datetime import datetime, time
from unittest import TestCase
from unittest.mock import patch

import main


class MainDegradationTest(TestCase):
    def test_main_sends_briefing_when_cptec_sources_are_unavailable(self):
        tide_payload = {
            "summary": "",
            "datum": "",
            "events": [
                {
                    "label": "Alta",
                    "datetime": datetime(2026, 4, 25, 1, 32, tzinfo=main.SALVADOR_TIMEZONE),
                    "height_m": 2.06,
                }
            ],
            "sunrise": time(5, 39),
            "sunset": time(17, 28),
            "upcoming_event": None,
        }
        moon_payload = {"phase": "Minguante", "moonrise": None, "moonset": None}
        sent_messages = []

        with (
            patch.dict(
                "os.environ",
                {"TELEGRAM_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"},
            ),
            patch.object(
                main,
                "fetch_weather",
                side_effect=main.FetchDataException("weather unavailable"),
            ),
            patch.object(
                main,
                "fetch_waves",
                side_effect=main.FetchDataException("waves unavailable"),
            ),
            patch.object(main, "fetch_tides", return_value=tide_payload),
            patch.object(main, "fetch_moon_data", return_value=moon_payload),
            patch.object(
                main,
                "notify_by_telegram",
                side_effect=lambda _token, _chat_id, message: sent_messages.append(message),
            ),
        ):
            result = main.main()

        self.assertEqual(result, main.ErrorCode.SUCCESS)
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("CLIMA\n- Indisponivel no momento", sent_messages[0])
        self.assertIn("MAR E VENTO\n- Indisponivel no momento", sent_messages[0])
        self.assertIn("MARE\n- Alta: 01:32 (2,06 m)", sent_messages[0])
