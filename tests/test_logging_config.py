import asyncio
import datetime
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import disnake

from cogs.server_logs import (
    LOG_ACTION_TITLES,
    LOG_CHANNELS,
    LOG_EMOJI_NAMES,
    ServerLogsCog,
    _build_log_components,
    _format_overwrites,
    _load_channel_overrides,
    _safe_text,
)


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


class LogComponentTests(unittest.TestCase):
    def test_permissions_are_rendered_as_readable_names(self) -> None:
        self.assertEqual(_safe_text(disnake.Permissions(1024)), "Просматривать каналы")

    def test_empty_flags_are_rendered_as_none(self) -> None:
        self.assertEqual(_safe_text(disnake.Permissions.none()), "Нет")

    def test_permission_overwrite_shows_allowed_and_denied_permissions(self) -> None:
        overwrite = disnake.PermissionOverwrite(view_channel=True, send_messages=False)

        self.assertEqual(
            _safe_text(overwrite),
            "Разрешено: Просматривать каналы; запрещено: Отправлять сообщения",
        )

    def test_channel_flags_are_rendered_as_readable_names(self) -> None:
        self.assertEqual(_safe_text(disnake.ChannelFlags(pinned=True)), "Закреплён")

    def test_unresolved_object_is_rendered_as_id(self) -> None:
        self.assertEqual(_safe_text(disnake.Object(id=123456789)), "ID `123456789`")

    def test_overwrites_are_rendered_vertically(self) -> None:
        role = MagicMock(id=123, mention="<@&123>")
        role.name = "Moderator"
        overwrite = disnake.PermissionOverwrite(view_channel=True, send_messages=False)

        self.assertEqual(
            _format_overwrites([(role, overwrite)]),
            "• <@&123> (`Moderator` · `123`)\n"
            "  Разрешено: Просматривать каналы\n"
            "  Запрещено: Отправлять сообщения",
        )

    def test_log_card_keeps_title_icon_and_groups_details(self) -> None:
        guild = MagicMock(id=123456789, icon=None)
        guild.name = "Test server"
        emoji = MagicMock()
        emoji.__str__.return_value = "<:voice:1>"

        components, overflow_text = _build_log_components(
            guild,
            "Вход в голосовой канал",
            ["**Участник** · <@123>", "**Канал** · <#456>"],
            "voice_join",
            {LOG_EMOJI_NAMES["voice_join"]: emoji},
        )

        self.assertIsNone(overflow_text)
        self.assertEqual(len(components), 7)
        self.assertIn("<:voice:1>", components[0].content)
        self.assertIn("Вход в голосовой канал", components[0].content)
        self.assertEqual(components[2].content, "**Участник** · <@123>")
        self.assertEqual(components[4].content, "**Канал** · <#456>")
        self.assertIn("Test server", components[6].content)
        self.assertNotIn("123456789", components[6].content)

    def test_log_timestamp_is_moved_to_footer(self) -> None:
        guild = MagicMock(id=123456789, icon=None)
        guild.name = "Test server"
        timestamp = 1794139200
        expected_time = datetime.datetime.fromtimestamp(timestamp).strftime(
            "%d.%m.%Y - %H:%M"
        )

        components, overflow_text = _build_log_components(
            guild,
            "Вход в голосовой канал",
            ["**Участник** · <@123>", f"**Время** · <t:{timestamp}:F>"],
            "voice_join",
        )

        self.assertIsNone(overflow_text)
        self.assertEqual(len(components), 5)
        self.assertNotIn("Время", components[0].content)
        self.assertEqual(components[2].content, "**Участник** · <@123>")
        self.assertIn(
            f"-# Сервер: **Test server** · {expected_time}",
            components[4].content,
        )
        self.assertNotIn("123456789", components[4].content)

    def test_oversized_details_are_attached_without_truncating_the_text_file(self) -> None:
        guild = MagicMock(id=123456789, icon=None)
        guild.name = "Test server"
        oversized_detail = "**Переопределения прав**\n" + ("Полное разрешение\n" * 300)

        components, overflow_text = _build_log_components(
            guild,
            "Удаление канала",
            ["**Исполнитель** · <@123>", oversized_detail],
            "channel_delete",
        )

        self.assertIsNotNone(overflow_text)
        self.assertIn(oversized_detail, overflow_text)
        self.assertIn(
            "Полная запись приложена файлом `server-log-details.txt`.",
            "\n".join(
                component.content
                for component in components
                if isinstance(component, disnake.ui.TextDisplay)
            ),
        )
        self.assertTrue(
            any(
                isinstance(component, disnake.ui.File)
                and component.file.url == "attachment://server-log-details.txt"
                for component in components
            )
        )
        self.assertLess(
            sum(
                len(component.content)
                for component in components
                if isinstance(component, disnake.ui.TextDisplay)
            ),
            3500,
        )

    def test_overflow_file_is_sent_as_a_separate_message(self) -> None:
        cog = ServerLogsCog(MagicMock())
        guild = MagicMock(id=123456789)
        channel = MagicMock()
        channel.send = AsyncMock()
        overflow_file = MagicMock(spec=disnake.File)

        with patch.object(
            cog,
            "_get_log_channel",
            new=AsyncMock(return_value=(channel, 987654321)),
        ):
            asyncio.run(
                cog._send_components(
                    guild,
                    [disnake.ui.TextDisplay("Log card")],
                    log_key="channel_delete",
                    context="test log",
                    files=[overflow_file],
                )
            )

        self.assertEqual(channel.send.await_count, 1)
        (card_call,) = channel.send.await_args_list
        self.assertIn("components", card_call.kwargs)
        self.assertEqual(card_call.kwargs["files"], [overflow_file])


if __name__ == "__main__":
    unittest.main()
