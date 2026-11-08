import asyncio
import datetime
import io
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import disnake
from disnake import ui
from disnake.ext import commands

logger = logging.getLogger(__name__)

DEFAULT_LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_DEFAULT", "0") or "0")

AUDIT_ACTION_TITLES = {
    "guild_update": "Изменение настроек сервера",
    "channel_create": "Создание канала",
    "channel_update": "Изменение канала",
    "channel_delete": "Удаление канала",
    "overwrite_create": "Создание доступа к каналу",
    "overwrite_update": "Изменение доступа к каналу",
    "overwrite_delete": "Удаление доступа к каналу",
    "kick": "Исключение участника",
    "member_prune": "Очистка неактивных участников",
    "ban": "Блокировка участника",
    "unban": "Разблокировка участника",
    "member_update": "Изменение участника",
    "member_role_update": "Изменение ролей участника",
    "bot_add": "Добавление бота",
    "role_create": "Создание роли",
    "role_update": "Изменение роли",
    "role_delete": "Удаление роли",
    "invite_create": "Создание приглашения",
    "invite_update": "Изменение приглашения",
    "invite_delete": "Удаление приглашения",
    "webhook_create": "Создание вебхука",
    "webhook_update": "Изменение вебхука",
    "webhook_delete": "Удаление вебхука",
    "emoji_create": "Создание эмодзи",
    "emoji_update": "Изменение эмодзи",
    "emoji_delete": "Удаление эмодзи",
    "message_delete": "Удаление сообщения",
    "message_bulk_delete": "Массовое удаление сообщений",
    "message_pin": "Закрепление сообщения",
    "message_unpin": "Открепление сообщения",
    "integration_create": "Добавление интеграции",
    "integration_update": "Изменение интеграции",
    "integration_delete": "Удаление интеграции",
    "stage_instance_create": "Создание сцены",
    "stage_instance_update": "Изменение сцены",
    "stage_instance_delete": "Удаление сцены",
    "sticker_create": "Создание стикера",
    "sticker_update": "Изменение стикера",
    "sticker_delete": "Удаление стикера",
    "guild_scheduled_event_create": "Создание события сервера",
    "guild_scheduled_event_update": "Изменение события сервера",
    "guild_scheduled_event_delete": "Удаление события сервера",
    "thread_create": "Создание ветки",
    "thread_update": "Изменение ветки",
    "thread_delete": "Удаление ветки",
    "application_command_permission_update": "Изменение прав команды",
    "soundboard_sound_create": "Добавление звука в звуковую панель",
    "soundboard_sound_update": "Изменение звука звуковой панели",
    "soundboard_sound_delete": "Удаление звука звуковой панели",
    "automod_rule_create": "Создание правила AutoMod",
    "automod_rule_update": "Изменение правила AutoMod",
    "automod_rule_delete": "Удаление правила AutoMod",
    "automod_block_message": "AutoMod заблокировал сообщение",
    "automod_send_alert_message": "AutoMod отправил предупреждение",
    "automod_timeout": "AutoMod выдал тайм-аут",
    "automod_quarantine_user": "AutoMod ограничил участника",
    "creator_monetization_request_created": "Запрос монетизации сервера",
    "creator_monetization_terms_accepted": "Принятие условий монетизации",
}

GATEWAY_ACTION_TITLES = {
    "voice_join": "Вход в голосовой канал",
    "voice_leave": "Выход из голосового канала",
    "voice_transition": "Самостоятельный переход между голосовыми каналами",
    "voice_move": "Перемещение участника между голосовыми каналами",
    "voice_disconnect": "Отключение участника от голосового канала",
    "voice_state": "Изменение состояния в голосовом канале",
    "member_join": "Вход участника на сервер",
    "member_leave": "Выход участника с сервера",
    "message_edit": "Изменение сообщения",
    "message_delete": "Удаление сообщения",
    "message_bulk_delete": "Массовое удаление сообщений",
    "reaction_add": "Добавление реакции",
    "reaction_remove": "Удаление реакции",
    "poll_vote_add": "Голос в опросе добавлен",
    "poll_vote_remove": "Голос из опроса удалён",
    "automod_execution": "Срабатывание AutoMod",
    "scheduled_event_subscribe": "Запись на событие",
    "scheduled_event_unsubscribe": "Отмена записи на событие",
}

DETAIL_ACTION_TITLES = {
    "voice_server_mute_on": "Микрофон участника заглушён модератором",
    "voice_server_mute_off": "Модератор включил микрофон участника",
    "voice_server_deaf_on": "Звук участника отключён модератором",
    "voice_server_deaf_off": "Модератор включил звук участника",
    "voice_self_mute_on": "Участник самостоятельно выключил микрофон",
    "voice_self_mute_off": "Участник самостоятельно включил микрофон",
    "voice_self_deaf_on": "Участник самостоятельно выключил звук",
    "voice_self_deaf_off": "Участник самостоятельно включил звук",
    "voice_stream_start": "Участник начал трансляцию",
    "voice_stream_stop": "Участник завершил трансляцию",
    "voice_video_start": "Участник включил камеру",
    "voice_video_stop": "Участник выключил камеру",
    "voice_suppress": "Участник переведён в зрители сцены",
    "voice_unsuppress": "Участнику разрешено говорить на сцене",
    "voice_request_speak": "Участник запросил слово на сцене",
    "voice_cancel_request": "Участник отменил запрос слова",
    "role_added": "Участнику выданы роли",
    "role_removed": "У участника сняты роли",
}

GATEWAY_LOG_ACTIONS = tuple(GATEWAY_ACTION_TITLES)
LOG_ACTION_TITLES = {
    **AUDIT_ACTION_TITLES,
    **GATEWAY_ACTION_TITLES,
    **DETAIL_ACTION_TITLES,
}


def _load_channel_overrides() -> dict[str, int]:
    raw_overrides = os.getenv("LOG_CHANNEL_OVERRIDES", "{}")
    try:
        overrides = json.loads(raw_overrides)
    except json.JSONDecodeError as error:
        raise ValueError("LOG_CHANNEL_OVERRIDES must be valid JSON") from error

    if not isinstance(overrides, dict):
        raise ValueError("LOG_CHANNEL_OVERRIDES must be a JSON object")

    unknown_actions = overrides.keys() - LOG_ACTION_TITLES.keys()
    if unknown_actions:
        actions = ", ".join(sorted(unknown_actions))
        raise ValueError(f"Unknown action(s) in LOG_CHANNEL_OVERRIDES: {actions}")

    parsed: dict[str, int] = {}
    for action, channel_id in overrides.items():
        if isinstance(channel_id, bool):
            raise ValueError(f"Channel ID for {action!r} must be a positive integer")
        try:
            parsed_channel_id = int(channel_id)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Channel ID for {action!r} must be a positive integer"
            ) from error
        if parsed_channel_id <= 0:
            raise ValueError(f"Channel ID for {action!r} must be a positive integer")
        parsed[action] = parsed_channel_id
    return parsed


_LOG_CHANNEL_OVERRIDES = _load_channel_overrides()

LOG_EMOJI_NAMES = {
    action: f"log_{action}"
    for action in LOG_ACTION_TITLES
}
LOG_EMOJI_NAMES.update(
    {
        "application_command_permission_update": "log_appcmd_permissions",
        "creator_monetization_request_created": "log_monet_request",
        "creator_monetization_terms_accepted": "log_monet_terms",
    }
)

# Override any individual value to route that action to a different channel.
LOG_CHANNELS = {
    "default": DEFAULT_LOG_CHANNEL_ID,
    **{
        action: _LOG_CHANNEL_OVERRIDES.get(action, DEFAULT_LOG_CHANNEL_ID)
        for action in LOG_ACTION_TITLES
    },
}

CHANGE_LABELS = {
    "name": "Название",
    "topic": "Тема",
    "description": "Описание",
    "reason": "Причина",
    "position": "Позиция",
    "type": "Тип",
    "nsfw": "18+",
    "slowmode_delay": "Медленный режим",
    "bitrate": "Битрейт",
    "user_limit": "Лимит участников",
    "permissions": "Права",
    "overwrites": "Переопределения прав",
    "roles": "Роли",
    "nick": "Никнейм",
    "mute": "Заглушён",
    "deaf": "Оглушён",
    "communication_disabled_until": "Тайм-аут до",
    "hoist": "Отображение отдельно",
    "mentionable": "Можно упоминать",
    "color": "Цвет",
    "colour": "Цвет",
    "owner": "Владелец",
    "channel": "Канал",
    "afk_channel": "AFK-канал",
    "verification_level": "Уровень проверки",
    "explicit_content_filter": "Фильтр контента",
    "default_auto_archive_duration": "Автоархивация",
    "archived": "Архивирована",
    "locked": "Закрыта",
    "invitable": "Можно приглашать",
    "available": "Доступен",
    "enabled": "Включено",
    "expires_at": "Истекает",
    "max_age": "Срок действия",
    "max_uses": "Лимит использований",
    "temporary": "Временное приглашение",
}

FLAG_LABELS = {
    "create_instant_invite": "Создавать приглашения",
    "kick_members": "Исключать участников",
    "ban_members": "Банить участников",
    "administrator": "Администратор",
    "manage_channels": "Управлять каналами",
    "manage_guild": "Управлять сервером",
    "add_reactions": "Добавлять реакции",
    "view_audit_log": "Просматривать журнал аудита",
    "priority_speaker": "Приоритетный режим голоса",
    "stream": "Видеотрансляция",
    "view_channel": "Просматривать каналы",
    "send_messages": "Отправлять сообщения",
    "send_tts_messages": "Отправлять сообщения Text-to-Speech",
    "manage_messages": "Управлять сообщениями",
    "embed_links": "Встраивать ссылки",
    "attach_files": "Прикреплять файлы",
    "read_message_history": "Просматривать историю сообщений",
    "mention_everyone": "Упоминать @everyone и @here",
    "external_emojis": "Использовать внешние эмодзи",
    "view_guild_insights": "Просматривать аналитику сервера",
    "connect": "Подключаться к голосовым каналам",
    "speak": "Говорить в голосовых каналах",
    "mute_members": "Отключать микрофоны участников",
    "deafen_members": "Отключать звук участникам",
    "move_members": "Перемещать участников",
    "use_voice_activation": "Использовать голосовую активацию",
    "change_nickname": "Менять свой никнейм",
    "manage_nicknames": "Управлять никнеймами",
    "manage_roles": "Управлять ролями",
    "manage_webhooks": "Управлять вебхуками",
    "manage_guild_expressions": "Управлять эмодзи и стикерами",
    "use_application_commands": "Использовать команды приложений",
    "request_to_speak": "Запрашивать право выступить",
    "manage_events": "Управлять событиями",
    "manage_threads": "Управлять ветками",
    "create_public_threads": "Создавать публичные ветки",
    "create_private_threads": "Создавать приватные ветки",
    "external_stickers": "Использовать внешние стикеры",
    "send_messages_in_threads": "Отправлять сообщения в ветках",
    "use_embedded_activities": "Запускать активности",
    "moderate_members": "Выдавать тайм-аут участникам",
    "view_creator_monetization_analytics": "Просматривать аналитику монетизации",
    "use_soundboard": "Использовать звуковую панель",
    "create_guild_expressions": "Создавать эмодзи и стикеры",
    "create_events": "Создавать события",
    "use_external_sounds": "Использовать внешние звуки",
    "send_voice_messages": "Отправлять голосовые сообщения",
    "send_polls": "Создавать опросы",
    "use_external_apps": "Использовать внешние приложения",
    "pin_messages": "Закреплять сообщения",
    "bypass_slowmode": "Обходить медленный режим",
    "pinned": "Закреплён",
    "require_tag": "Требовать тег",
    "hide_media_download_options": "Скрывать скачивание медиа",
}


@dataclass
class PendingVoiceLog:
    member: disnake.Member
    before_channel: disnake.abc.GuildChannel | None
    after_channel: disnake.abc.GuildChannel | None
    action: disnake.AuditLogAction | None
    created_at: datetime.datetime


def _safe_text(value: Any, limit: int = 450) -> str:
    if value is None:
        text = "—"
    elif isinstance(value, bool):
        text = "Да" if value else "Нет"
    elif isinstance(value, disnake.PermissionOverwrite):
        allow, deny = value.pair()
        allowed = _format_flags(allow)
        denied = _format_flags(deny)
        text = f"Разрешено: {allowed}; запрещено: {denied}"
    elif isinstance(value, disnake.flags.BaseFlags):
        text = _format_flags(value)
    elif isinstance(value, (list, tuple, set)):
        text = ", ".join(_safe_text(item, 100) for item in value) or "—"
    else:
        mention = getattr(value, "mention", None)
        name = getattr(value, "name", None)
        identifier = getattr(value, "id", None)
        if mention and identifier is not None:
            safe_name = str(name or value).replace("`", "ˋ")
            text = f"{mention} (`{safe_name}` · `{identifier}`)"
        elif isinstance(value, disnake.Object):
            text = f"ID `{value.id}`"
        else:
            text = str(value).replace("`", "ˋ")
    text = text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_flags(value: disnake.flags.BaseFlags) -> str:
    enabled = [
        FLAG_LABELS.get(name, name.replace("_", " ").capitalize())
        for name, is_enabled in value
        if is_enabled
    ]
    return ", ".join(enabled) or "Нет"


def _format_overwrites(value: Any) -> str:
    if value is None:
        return "—"
    if not isinstance(value, (list, tuple)):
        return _safe_text(value)
    if not value:
        return "—"

    lines = []
    for target, overwrite in value:
        allow, deny = overwrite.pair()
        lines.extend(
            (
                f"• {_safe_text(target, 150)}",
                f"  Разрешено: {_format_flags(allow)}",
                f"  Запрещено: {_format_flags(deny)}",
            )
        )
    return "\n".join(lines)


def _get_audit_target(entry: disnake.AuditLogEntry) -> Any:
    if entry.action.target_type == "role" and entry._target_id is None:
        return None
    return entry.target


def _format_role_mentions(roles: Any) -> str:
    if not isinstance(roles, (list, tuple, set)):
        return _safe_text(roles)
    mentions = [
        f"<@&{role.id}>" if getattr(role, "id", None) is not None else _safe_text(role, 100)
        for role in roles
    ]
    return ", ".join(mentions) or "—"


def _build_log_components(
    guild: disnake.Guild,
    title: str,
    details: list[str],
    log_key: str,
    application_emojis: dict[str, disnake.Emoji] | None = None,
) -> tuple[list[ui.Component], str | None]:
    emoji_name = LOG_EMOJI_NAMES.get(log_key)
    emoji = application_emojis.get(emoji_name) if application_emojis and emoji_name else None
    icon = f"{emoji} " if emoji is not None else ""
    header = f"## {icon}**{_safe_text(title, 150)}**"
    detail_rows: list[str] = []
    timestamp = int(disnake.utils.utcnow().timestamp())
    for detail in details:
        timestamp_match = re.fullmatch(r"\*\*Время\*\* · <t:(\d+):F>", detail)
        if timestamp_match:
            timestamp = int(timestamp_match.group(1))
            continue
        detail_rows.append(detail)

    formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime(
        "%d.%m.%Y - %H:%M"
    )
    footer = f"-# Сервер: **{_safe_text(guild.name, 150)}** · {formatted_time}"
    full_text = (
        f"{title}\nСервер: {guild.name} · {formatted_time}\n\n"
        + "\n\n".join(detail_rows)
    )
    needs_attachment = (
        len(detail_rows) > 12
        or any(len(row) > 1000 for row in detail_rows)
        or sum(map(len, detail_rows)) + max(len(detail_rows) - 1, 0) > 3500
    )
    if needs_attachment:
        logger.warning(
            "Audit log details exceed component limits for guild %s action %s; "
            "full details will be attached as text",
            guild.id,
            log_key,
        )

    rows: list[str] = []
    body_limit = 2500 if needs_attachment else 3500
    body_length = 0
    for detail in detail_rows[:12]:
        row = detail[:1000]
        separator_length = 1 if rows else 0
        available = body_limit - body_length - separator_length
        if len(row) > available:
            if available > 0:
                rows.append(row[: max(available - 1, 0)] + "…")
            break
        rows.append(row)
        body_length += len(row) + separator_length

    if needs_attachment:
        rows.append("Полная запись приложена файлом `server-log-details.txt`.")

    components: list[ui.Component] = [ui.TextDisplay(header)]
    for row in rows:
        components.append(
            ui.Separator(divider=True, spacing=disnake.SeparatorSpacing.small)
        )
        components.append(ui.TextDisplay(row))
    if needs_attachment:
        components.append(ui.File(file="attachment://server-log-details.txt"))
    components.append(
        ui.Separator(divider=True, spacing=disnake.SeparatorSpacing.small)
    )
    components.append(ui.TextDisplay(footer))
    return components, full_text if needs_attachment else None


class ServerLogsCog(commands.Cog, name="Логи сервера"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending_voice_logs: dict[int, list[PendingVoiceLog]] = {}
        self._voice_log_tasks: dict[int, asyncio.Task] = {}
        self._voice_audit_counts: dict[tuple[int, int], tuple[int, datetime.datetime]] = {}
        self._voice_audit_baselined: set[int] = set()
        self._voice_audit_baseline_ready = asyncio.Event()
        self._audit_permission_warnings: set[int] = set()
        self._application_emojis: dict[str, disnake.Emoji] = {}
        self._application_emojis_last_fetch = 0.0
        self._application_emojis_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        if self.bot.is_ready():
            await self._initialize_audit_baseline()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._initialize_audit_baseline()
        await self._refresh_application_emojis(force=True)
        for guild in self.bot.guilds:
            bot_member = guild.me
            if (
                bot_member is not None
                and not bot_member.guild_permissions.view_audit_log
                and guild.id not in self._audit_permission_warnings
            ):
                logger.warning(
                    "Full server audit logging is unavailable in guild %s: "
                    "the bot is missing VIEW_AUDIT_LOG",
                    guild.id,
                )
                self._audit_permission_warnings.add(guild.id)

    async def _refresh_application_emojis(self, *, force: bool = False) -> None:
        loop = asyncio.get_running_loop()
        if (
            not force
            and loop.time() - self._application_emojis_last_fetch < 30
        ):
            return

        async with self._application_emojis_lock:
            if (
                not force
                and loop.time() - self._application_emojis_last_fetch < 30
            ):
                return
            try:
                emojis = await self.bot.fetch_application_emojis()
            except disnake.HTTPException:
                logger.exception("Could not fetch application emojis for log headings")
                self._application_emojis_last_fetch = loop.time()
                return

            self._application_emojis = {
                emoji.name: emoji for emoji in emojis if emoji.name is not None
            }
            self._application_emojis_last_fetch = loop.time()
            missing = set(LOG_EMOJI_NAMES.values()) - self._application_emojis.keys()
            logger.info(
                "Loaded %s application emojis for log headings; %s action icons missing",
                len(self._application_emojis),
                len(missing),
            )

    async def _initialize_audit_baseline(self) -> None:
        self._voice_audit_baseline_ready.clear()
        try:
            for guild in self.bot.guilds:
                await self._prime_voice_audit_counts(guild)
        finally:
            self._voice_audit_baseline_ready.set()

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: disnake.AuditLogEntry) -> None:
        if entry.action in (
            disnake.AuditLogAction.member_move,
            disnake.AuditLogAction.member_disconnect,
        ):
            return

        action_name = entry.action.name
        title = AUDIT_ACTION_TITLES.get(
            action_name,
            "Действие аудита: " + action_name.replace("_", " "),
        )
        actor_details = [
            f"**Исполнитель** · {_safe_text(entry.user)}",
            f"**Объект** · {_safe_text(_get_audit_target(entry))}",
        ]
        details = list(actor_details)
        handled_change_keys: set[str] = set()
        specific_logs_sent = False
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}

        changes = entry.changes
        if changes is not None:
            before = dict(changes.before)
            after = dict(changes.after)

            if "roles" in before or "roles" in after:
                added_roles = after.get("roles")
                removed_roles = before.get("roles")
                if added_roles:
                    role_details = [
                        actor_details[0],
                        f"**Участник** · {_safe_text(_get_audit_target(entry))}",
                        f"**Добавлены роли** · {_format_role_mentions(added_roles)}",
                    ]
                    if entry.reason:
                        role_details.append(f"**Причина** · {_safe_text(entry.reason)}")
                    await self._send_log(
                        entry.guild,
                        DETAIL_ACTION_TITLES["role_added"],
                        role_details,
                        log_key="role_added",
                    )
                    specific_logs_sent = True
                if removed_roles:
                    role_details = [
                        actor_details[0],
                        f"**Участник** · {_safe_text(_get_audit_target(entry))}",
                        f"**Сняты роли** · {_format_role_mentions(removed_roles)}",
                    ]
                    if entry.reason:
                        role_details.append(f"**Причина** · {_safe_text(entry.reason)}")
                    await self._send_log(
                        entry.guild,
                        DETAIL_ACTION_TITLES["role_removed"],
                        role_details,
                        log_key="role_removed",
                    )
                    specific_logs_sent = True
                handled_change_keys.add("roles")

            if action_name == "member_update":
                for attribute, state in (("mute", "mute"), ("deaf", "deaf")):
                    old_value = before.get(attribute)
                    new_value = after.get(attribute)
                    if (
                        not isinstance(old_value, bool)
                        or not isinstance(new_value, bool)
                        or old_value == new_value
                    ):
                        continue

                    action_key = f"voice_server_{state}_{'on' if new_value else 'off'}"
                    state_label = "микрофон" if state == "mute" else "звук"
                    action_details = [
                        actor_details[0],
                        f"**Участник** · {_safe_text(_get_audit_target(entry))}",
                        f"**Действие** · {'Заглушил' if new_value else 'Снял заглушение с'} {state_label}",
                    ]
                    if entry.reason:
                        action_details.append(
                            f"**Причина** · {_safe_text(entry.reason)}"
                        )
                    await self._send_log(
                        entry.guild,
                        DETAIL_ACTION_TITLES[action_key],
                        action_details,
                        log_key=action_key,
                    )
                    handled_change_keys.add(attribute)
                    specific_logs_sent = True

            for key in dict.fromkeys((*before.keys(), *after.keys())):
                if key in handled_change_keys:
                    continue
                if key == "roles":
                    continue

                label = CHANGE_LABELS.get(key, key.replace("_", " ").capitalize())
                if key == "overwrites":
                    old = _format_overwrites(before.get(key))
                    new = _format_overwrites(after.get(key))
                    details.append(
                        f"**{label}**\nДо:\n{old}\nПосле:\n{new}"
                    )
                    continue
                old = _safe_text(before.get(key))
                new = _safe_text(after.get(key))
                details.append(f"**{label}** · {old} → {new}")

        extra = entry.extra
        if extra is not None:
            extra_values = vars(extra) if hasattr(extra, "__dict__") else {}
            for key, value in extra_values.items():
                if key.startswith("_") or value is None:
                    continue
                label = CHANGE_LABELS.get(key, key.replace("_", " ").capitalize())
                details.append(f"**{label}** · {_safe_text(value)}")

        if entry.reason:
            details.append(f"**Причина** · {_safe_text(entry.reason)}")
        details.append(f"**Время** · <t:{int(entry.created_at.timestamp())}:F>")
        if specific_logs_sent and not any(
            key not in handled_change_keys for key in (*before.keys(), *after.keys())
        ):
            return
        await self._send_log(entry.guild, title, details, log_key=action_name)

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member) -> None:
        await self._send_log(
            member.guild,
            "Вход участника на сервер",
            [
                f"**Участник** · {_safe_text(member)}",
                f"**Создан аккаунт** · <t:{int(member.created_at.timestamp())}:F>",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key="member_join",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: disnake.Member) -> None:
        await self._send_log(
            member.guild,
            "Выход участника с сервера",
            [
                f"**Участник** · {_safe_text(member)}",
                "**Инициатор** · Не определён; подробности могут быть в журнале аудита",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key="member_leave",
        )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: disnake.RawMessageUpdateEvent) -> None:
        if (
            payload.guild_id is None
            or self._is_log_channel(payload.channel_id)
            or "content" not in payload.data
        ):
            return

        before = payload.cached_message
        after_content = payload.data.get("content")
        author_id = (
            before.author.id
            if before is not None
            else (payload.data.get("author") or {}).get("id")
        )
        if before is not None and before.author.bot:
            return
        if before is not None and before.content == after_content:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = self.bot.get_channel(payload.channel_id)
        author = (
            before.author
            if before is not None
            else f"<@{author_id}> (`{author_id}`)" if author_id else "Не определён"
        )
        before_content = before.content if before is not None else "(не было в кэше)"
        message_url = (
            f"https://discord.com/channels/{payload.guild_id}/"
            f"{payload.channel_id}/{payload.message_id}"
        )
        await self._send_log(
            guild,
            "Изменение сообщения",
            [
                f"**Автор** · {_safe_text(author or 'Не определён')}",
                f"**Канал** · {_safe_text(channel or f'ID {payload.channel_id}')}",
                f"**Было** · {_safe_text(before_content or '(без текста)', 700)}",
                f"**Стало** · {_safe_text(after_content or '(без текста)', 700)}",
                f"**Ссылка** · [Открыть сообщение]({message_url})",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key="message_edit",
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: disnake.RawMessageDeleteEvent) -> None:
        if payload.guild_id is None or self._is_log_channel(payload.channel_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        cached = payload.cached_message
        if cached is not None and cached.author.bot:
            return
        author = _safe_text(cached.author) if cached is not None else "Не определён"
        content = (
            _safe_text(cached.content or "(без текста)", 700)
            if cached is not None
            else "Текст не был в кэше"
        )
        message_url = (
            f"https://discord.com/channels/{payload.guild_id}/"
            f"{payload.channel_id}/{payload.message_id}"
        )
        await self._send_log(
            guild,
            "Удаление сообщения",
            [
                f"**Автор** · {author}",
                f"**Канал** · {_safe_text(self.bot.get_channel(payload.channel_id) or f'ID {payload.channel_id}')}",
                f"**Сообщение** · {content}",
                "**Инициатор** · Не определён по Gateway; аудит может содержать исполнителя",
                f"**Ссылка** · {message_url}",
            ],
            log_key="message_delete",
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self, payload: disnake.RawBulkMessageDeleteEvent
    ) -> None:
        if payload.guild_id is None or self._is_log_channel(payload.channel_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        await self._send_log(
            guild,
            "Массовое удаление сообщений",
            [
                f"**Канал** · {_safe_text(self.bot.get_channel(payload.channel_id) or f'ID {payload.channel_id}')}",
                f"**Количество** · {len(payload.message_ids)}",
                "**Инициатор** · Не определён по Gateway; аудит может содержать исполнителя",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key="message_bulk_delete",
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: disnake.Member,
        before: disnake.VoiceState,
        after: disnake.VoiceState,
    ) -> None:
        if member.bot:
            return

        before_channel = before.channel
        after_channel = after.channel
        if before_channel != after_channel:
            if before_channel is not None and after_channel is not None:
                action = disnake.AuditLogAction.member_move
            elif before_channel is not None:
                action = disnake.AuditLogAction.member_disconnect
            else:
                action = None
            self._queue_voice_log(
                PendingVoiceLog(
                    member=member,
                    before_channel=before_channel,
                    after_channel=after_channel,
                    action=action,
                    created_at=disnake.utils.utcnow(),
                )
            )
            return

        voice_state_actions = (
            ("self_mute", "voice_self_mute", "Микрофон"),
            ("self_deaf", "voice_self_deaf", "Звук"),
            ("self_stream", "voice_stream", "Трансляция"),
            ("self_video", "voice_video", "Камера"),
        )
        timestamp = int(disnake.utils.utcnow().timestamp())
        channel = after.channel or before.channel
        for attribute, action_prefix, label in voice_state_actions:
            old_value = getattr(before, attribute)
            new_value = getattr(after, attribute)
            if old_value == new_value:
                continue
            action_key = f"{action_prefix}_{'start' if new_value else 'stop'}"
            if attribute in ("self_mute", "self_deaf"):
                action_key = f"{action_prefix}_{'on' if new_value else 'off'}"
            title = DETAIL_ACTION_TITLES[action_key]
            state_text = (
                "Участник самостоятельно выключил"
                if new_value and attribute in ("self_mute", "self_deaf")
                else "Участник самостоятельно включил"
                if attribute in ("self_mute", "self_deaf")
                else "Включено"
                if new_value
                else "Выключено"
            )
            await self._send_log(
                member.guild,
                title,
                [
                    f"**Участник** · {_safe_text(member)}",
                    f"**Канал** · {_safe_text(channel)}",
                    f"**{label}** · {state_text}",
                    f"**Время** · <t:{timestamp}:F>",
                ],
                log_key=action_key,
            )

        if before.suppress != after.suppress:
            action_key = "voice_suppress" if after.suppress else "voice_unsuppress"
            await self._send_log(
                member.guild,
                DETAIL_ACTION_TITLES[action_key],
                [
                    f"**Участник** · {_safe_text(member)}",
                    f"**Канал** · {_safe_text(channel)}",
                    f"**Статус сцены** · {'Зритель' if after.suppress else 'Может говорить'}",
                    f"**Время** · <t:{timestamp}:F>",
                ],
                log_key=action_key,
            )

        if before.requested_to_speak_at != after.requested_to_speak_at:
            action_key = (
                "voice_request_speak"
                if after.requested_to_speak_at is not None
                else "voice_cancel_request"
            )
            await self._send_log(
                member.guild,
                DETAIL_ACTION_TITLES[action_key],
                [
                    f"**Участник** · {_safe_text(member)}",
                    f"**Канал** · {_safe_text(channel)}",
                    f"**Время** · <t:{timestamp}:F>",
                ],
                log_key=action_key,
            )

    def _queue_voice_log(self, change: PendingVoiceLog) -> None:
        guild_id = change.member.guild.id
        self._pending_voice_logs.setdefault(guild_id, []).append(change)
        task = self._voice_log_tasks.get(guild_id)
        if task is None or task.done():
            self._voice_log_tasks[guild_id] = self.bot.loop.create_task(
                self._flush_voice_logs(guild_id)
            )

    async def _flush_voice_logs(self, guild_id: int) -> None:
        await self._voice_audit_baseline_ready.wait()
        while self._pending_voice_logs.get(guild_id):
            changes = self._pending_voice_logs.pop(guild_id)
            guild = changes[0].member.guild
            actors: dict[int, disnake.AuditLogEntry] = {}
            audit_available = False
            unresolved = [
                index for index, change in enumerate(changes)
                if change.action is not None
            ]

            if unresolved:
                await asyncio.sleep(0.5)
                for attempt in range(3):
                    if attempt:
                        await asyncio.sleep(0.5)
                    audit_entries = await self._fetch_voice_audit_entries(guild)
                    if audit_entries is None:
                        continue
                    audit_available = True
                    new_assignments = self._match_voice_audit_entries(
                        guild_id,
                        [changes[index] for index in unresolved],
                        audit_entries,
                    )
                    for local_index, entry in new_assignments.items():
                        actors[unresolved[local_index]] = entry
                    unresolved = [
                        index for index in unresolved if index not in actors
                    ]
                    if not unresolved:
                        break

            for index, change in enumerate(changes):
                await self._send_voice_log(
                    change,
                    actors.get(index),
                    audit_available=audit_available,
                )
            if self._pending_voice_logs.get(guild_id):
                await asyncio.sleep(1)
        self._voice_log_tasks.pop(guild_id, None)

    async def _fetch_voice_audit_entries(
        self, guild: disnake.Guild
    ) -> list[disnake.AuditLogEntry] | None:
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.view_audit_log:
            if guild.id not in self._audit_permission_warnings:
                logger.warning(
                    "Voice logging cannot identify moderators in guild %s: "
                    "the bot is missing VIEW_AUDIT_LOG",
                    guild.id,
                )
                self._audit_permission_warnings.add(guild.id)
            return None

        try:
            return [entry async for entry in guild.audit_logs(limit=50)]
        except disnake.Forbidden:
            logger.warning(
                "Voice logging could not read audit log for guild %s: Discord returned 403",
                guild.id,
            )
        except disnake.HTTPException:
            logger.exception(
                "Voice logging failed to fetch audit log for guild %s", guild.id
            )
        return None

    async def _prime_voice_audit_counts(self, guild: disnake.Guild) -> None:
        entries = await self._fetch_voice_audit_entries(guild)
        if entries is None:
            return
        now = disnake.utils.utcnow()
        for entry in entries:
            if entry.action not in (
                disnake.AuditLogAction.member_move,
                disnake.AuditLogAction.member_disconnect,
            ):
                continue
            count = max(1, int(getattr(entry.extra, "count", 1)))
            self._voice_audit_counts[(guild.id, entry.id)] = (count, now)
        self._voice_audit_baselined.add(guild.id)
        logger.info("Initialized voice audit count baseline for guild %s", guild.id)

    def _match_voice_audit_entries(
        self,
        guild_id: int,
        changes: list[PendingVoiceLog],
        entries: list[disnake.AuditLogEntry],
    ) -> dict[int, disnake.AuditLogEntry]:
        now = disnake.utils.utcnow()
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            if entry.action not in (
                disnake.AuditLogAction.member_move,
                disnake.AuditLogAction.member_disconnect,
            ):
                continue
            count = max(1, int(getattr(entry.extra, "count", 1)))
            key = (guild_id, entry.id)
            previous = self._voice_audit_counts.get(key)
            previous_count = (
                previous[0]
                if previous is not None
                else 0 if guild_id in self._voice_audit_baselined else count
            )
            remaining = max(0, count - previous_count)
            if remaining:
                candidates.append(
                    {
                        "entry": entry,
                        "key": key,
                        "count": count,
                        "previous_count": previous_count,
                        "remaining": remaining,
                    }
                )

        if guild_id not in self._voice_audit_baselined:
            self._voice_audit_baselined.add(guild_id)
            logger.warning(
                "Voice audit counts for guild %s were not primed; "
                "current entries are being used as baseline without attribution",
                guild_id,
            )
            return {}

        assignments: dict[int, disnake.AuditLogEntry] = {}
        unassigned = set(range(len(changes)))

        def matches(
            change: PendingVoiceLog, candidate: dict[str, Any]
        ) -> bool:
            entry = candidate["entry"]
            if change.action != entry.action:
                return False
            if change.action == disnake.AuditLogAction.member_move:
                target_channel = getattr(entry.extra, "channel", None)
                if target_channel is not None and change.after_channel is not None:
                    return target_channel.id == change.after_channel.id
            target_id = getattr(getattr(entry, "target", None), "id", None)
            return target_id is None or change.member.id == target_id

        for candidate in candidates:
            if candidate["remaining"] <= 0:
                continue
            eligible = [
                index for index in unassigned if matches(changes[index], candidate)
            ]
            eligible = [
                index
                for index in eligible
                if sum(
                    other["remaining"] > 0 and matches(changes[index], other)
                    for other in candidates
                )
                == 1
            ]
            if not eligible:
                continue
            matched_indexes = eligible[:candidate["remaining"]]
            for index in matched_indexes:
                assignments[index] = candidate["entry"]
                unassigned.remove(index)
            self._voice_audit_counts[candidate["key"]] = (
                candidate["previous_count"] + len(matched_indexes),
                now,
            )
        return assignments

    async def _send_voice_log(
        self,
        change: PendingVoiceLog,
        audit_entry: disnake.AuditLogEntry | None,
        *,
        audit_available: bool,
    ) -> None:
        member_text = f"{change.member.mention} (`{change.member.id}`)"
        timestamp = int(change.created_at.timestamp())
        details = [f"**Участник** · {member_text}"]

        if change.before_channel is None and change.after_channel is not None:
            title = "Вход в канал"
            log_key = "voice_join"
            details.append(
                f"**Канал** · {change.after_channel.mention} "
                f"(`{change.after_channel.name}` · `{change.after_channel.id}`)"
            )
        elif change.after_channel is None and change.before_channel is not None:
            title = (
                "Отключение от канала"
                if audit_entry is not None and audit_entry.user is not None
                else "Выход с канала"
            )
            log_key = (
                "voice_disconnect"
                if audit_entry is not None and audit_entry.user is not None
                else "voice_leave"
            )
            details.append(
                f"**Канал** · {change.before_channel.mention} "
                f"(`{change.before_channel.name}` · `{change.before_channel.id}`)"
            )
            if audit_entry is not None and audit_entry.user is not None:
                actor = audit_entry.user
                details.append(f"**Отключил** · <@{actor.id}> (`{actor.id}`)")
        elif change.before_channel is not None and change.after_channel is not None:
            title = "Перемещение пользователя" if audit_entry is not None else "Переход"
            log_key = "voice_move" if audit_entry is not None else "voice_transition"
            details.extend(
                (
                    f"**Откуда** · {change.before_channel.mention} "
                    f"(`{change.before_channel.name}` · `{change.before_channel.id}`)",
                    f"**Куда** · {change.after_channel.mention} "
                    f"(`{change.after_channel.name}` · `{change.after_channel.id}`)",
                )
            )
            if audit_entry is not None and audit_entry.user is not None:
                actor = audit_entry.user
                details.append(f"**Кто переместил** · <@{actor.id}> (`{actor.id}`)")
            elif audit_entry is None and not audit_available:
                details.append("**Инициатор** · Нет доступа к журналу аудита")
        else:
            logger.error(
                "Received voice state change without channels for member %s",
                change.member.id,
            )
            return

        details.append(f"**Время** · <t:{timestamp}:F>")
        if audit_entry is not None and audit_entry.reason:
            details.append(f"**Причина** · {_safe_text(audit_entry.reason, 500)}")
        emoji_name = LOG_EMOJI_NAMES.get(log_key)
        if emoji_name and emoji_name not in self._application_emojis:
            await self._refresh_application_emojis()
        components, overflow_text = _build_log_components(
            change.member.guild, title, details, log_key, self._application_emojis
        )
        await self._send_components(
            change.member.guild,
            components,
            log_key=log_key,
            context=f"voice log for member {change.member.id}",
            files=(
                [
                    disnake.File(
                        io.BytesIO(overflow_text.encode("utf-8")),
                        filename="server-log-details.txt",
                    )
                ]
                if overflow_text is not None
                else None
            ),
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: disnake.RawReactionActionEvent
    ) -> None:
        await self._log_reaction(payload, "Добавлена реакция", "reaction_add")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: disnake.RawReactionActionEvent
    ) -> None:
        await self._log_reaction(payload, "Удалена реакция", "reaction_remove")

    @commands.Cog.listener()
    async def on_raw_poll_vote_add(
        self, payload: disnake.RawPollVoteActionEvent
    ) -> None:
        await self._log_poll_vote(payload, "Голос в опросе добавлен", "poll_vote_add")

    @commands.Cog.listener()
    async def on_raw_poll_vote_remove(
        self, payload: disnake.RawPollVoteActionEvent
    ) -> None:
        await self._log_poll_vote(payload, "Голос из опроса удалён", "poll_vote_remove")

    async def _log_poll_vote(
        self, payload: disnake.RawPollVoteActionEvent, title: str, log_key: str
    ) -> None:
        if payload.guild_id is None or self._is_log_channel(payload.channel_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        user = self.bot.get_user(payload.user_id)
        if user is not None and user.bot:
            return
        url = (
            f"https://discord.com/channels/{payload.guild_id}/"
            f"{payload.channel_id}/{payload.message_id}"
        )
        await self._send_log(
            guild,
            title,
            [
                f"**Участник** · {_safe_text(user or f'ID {payload.user_id}')}",
                f"**Вариант** · `{payload.answer_id}`",
                f"**Опрос** · [Открыть сообщение]({url})",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key=log_key,
        )

    async def _log_reaction(
        self, payload: disnake.RawReactionActionEvent, title: str, log_key: str
    ) -> None:
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if guild is None or self._is_log_channel(payload.channel_id):
            return
        user = payload.member or self.bot.get_user(payload.user_id)
        if user is not None and user.bot:
            return
        channel = self.bot.get_channel(payload.channel_id)
        url = (
            f"https://discord.com/channels/{guild.id}/"
            f"{payload.channel_id}/{payload.message_id}"
        )
        await self._send_log(
            guild,
            title,
            [
                f"**Участник** · {_safe_text(user or f'ID {payload.user_id}')}",
                f"**Реакция** · {_safe_text(payload.emoji)}",
                f"**Канал** · {_safe_text(channel or f'ID {payload.channel_id}')}",
                f"**Сообщение** · [Открыть сообщение]({url})",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key=log_key,
        )

    @commands.Cog.listener()
    async def on_automod_action_execution(
        self, event: disnake.AutoModActionExecution
    ) -> None:
        details = [
            f"**Участник** · {_safe_text(event.user or f'ID {event.user_id}')}",
            f"**Правило** · `{event.rule_id}`",
            f"**Действие** · {_safe_text(event.action)}",
            f"**Канал** · {_safe_text(event.channel)}",
            f"**Сообщение** · {_safe_text(event.content or '(недоступно)', 700)}",
            f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
        ]
        await self._send_log(
            event.guild, "Срабатывание AutoMod", details, log_key="automod_execution"
        )

    @commands.Cog.listener()
    async def on_guild_scheduled_event_subscribe(
        self, event: disnake.GuildScheduledEvent, user: disnake.User
    ) -> None:
        await self._log_scheduled_event_subscription(
            event, user, "Запись на событие", "scheduled_event_subscribe"
        )

    @commands.Cog.listener()
    async def on_guild_scheduled_event_unsubscribe(
        self, event: disnake.GuildScheduledEvent, user: disnake.User
    ) -> None:
        await self._log_scheduled_event_subscription(
            event, user, "Отмена записи на событие", "scheduled_event_unsubscribe"
        )

    async def _log_scheduled_event_subscription(
        self,
        event: disnake.GuildScheduledEvent,
        user: disnake.User,
        title: str,
        log_key: str,
    ) -> None:
        await self._send_log(
            event.guild,
            title,
            [
                f"**Участник** · {_safe_text(user)}",
                f"**Событие** · {_safe_text(event)} (`{event.id}`)",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            ],
            log_key=log_key,
        )

    @staticmethod
    def _is_log_channel(channel_id: int) -> bool:
        return channel_id in LOG_CHANNELS.values()

    async def _get_log_channel(self, log_key: str) -> tuple[Any, int] | tuple[None, int]:
        channel_id = LOG_CHANNELS.get(log_key, DEFAULT_LOG_CHANNEL_ID)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except disnake.NotFound:
                logger.error("Log channel %s does not exist (action %s)", channel_id, log_key)
                return None, channel_id
            except disnake.Forbidden:
                logger.error(
                    "Bot cannot access log channel %s (action %s)", channel_id, log_key
                )
                return None, channel_id
            except disnake.HTTPException:
                logger.exception(
                    "Could not fetch log channel %s (action %s)", channel_id, log_key
                )
                return None, channel_id

        if not hasattr(channel, "send"):
            logger.error(
                "Configured log channel %s is not messageable (action %s)",
                channel_id,
                log_key,
            )
            return None, channel_id
        return channel, channel_id

    async def _send_components(
        self,
        guild: disnake.Guild,
        components: list[ui.Component],
        *,
        log_key: str,
        context: str,
        files: list[disnake.File] | None = None,
    ) -> None:
        channel, channel_id = await self._get_log_channel(log_key)
        if channel is None:
            return
        try:
            await channel.send(
                components=[ui.Container(*components)],
                allowed_mentions=disnake.AllowedMentions.none(),
                files=files,
            )
        except disnake.Forbidden:
            logger.error(
                "Bot cannot send %s to log channel %s", context, channel_id
            )
        except disnake.HTTPException:
            logger.exception(
                "Failed to send %s for guild %s", context, guild.id
            )

    async def _send_log(
        self,
        guild: disnake.Guild,
        title: str,
        details: list[str],
        *,
        log_key: str = "default",
    ) -> None:
        emoji_name = LOG_EMOJI_NAMES.get(log_key)
        if emoji_name and emoji_name not in self._application_emojis:
            await self._refresh_application_emojis()
        components, overflow_text = _build_log_components(
            guild, title, details, log_key, self._application_emojis
        )
        await self._send_components(
            guild,
            components,
            log_key=log_key,
            context=f"server log '{title}'",
            files=(
                [
                    disnake.File(
                        io.BytesIO(overflow_text.encode("utf-8")),
                        filename="server-log-details.txt",
                    )
                ]
                if overflow_text is not None
                else None
            ),
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(ServerLogsCog(bot))
