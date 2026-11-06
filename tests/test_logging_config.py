import json
import os
import unittest
from unittest.mock import patch

from cogs.server_logs import LOG_ACTION_TITLES, LOG_CHANNELS, _load_channel_overrides


class LogChannelConfigTests(unittest.TestCase):
    def test_all_actions_have_default_channel_routes(self) -> None:
        self.assertEqual(set(LOG_CHANNELS) - {"default"}, set(LOG_ACTION_TITLES))

    def test_channel_overrides_accept_known_actions(self) -> None:
        overrides = {"voice_join": "123456789012345678"}
        with patch.dict(
            os.environ, {"LOG_CHANNEL_OVERRIDES": json.dumps(overrides)}, clear=False
        ):
            self.assertEqual(
                _load_channel_overrides(),
                {"voice_join": 123456789012345678},
            )

    def test_unknown_action_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"LOG_CHANNEL_OVERRIDES": '{"not_a_log_action":123}'},
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown action"):
                _load_channel_overrides()

    def test_invalid_json_is_rejected(self) -> None:
        with patch.dict(
            os.environ, {"LOG_CHANNEL_OVERRIDES": "{invalid"}, clear=False
        ):
            with self.assertRaisesRegex(ValueError, "valid JSON"):
                _load_channel_overrides()

    def test_non_positive_channel_id_is_rejected(self) -> None:
        with patch.dict(
            os.environ, {"LOG_CHANNEL_OVERRIDES": '{"voice_join":0}'}, clear=False
        ):
            with self.assertRaisesRegex(ValueError, "positive integer"):
                _load_channel_overrides()


if __name__ == "__main__":
    unittest.main()
