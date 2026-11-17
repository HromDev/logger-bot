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
from disnake.ext import commands, tasks

from cogs.message_store import (
    MessageStore,
    StoredAttachment,
    StoredMessage,
    safe_filename,
)

logger = logging.getLogger(__name__)

DEFAULT_LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_DEFAULT", "0") or "0")
MESSAGE_CACHE_DIR = os.getenv("MESSAGE_CACHE_DIR", "").strip() or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
MESSAGE_CACHE_DAYS = float(os.getenv("MESSAGE_CACHE_DAYS", "14") or "14")
MESSAGE_CACHE_MAX_FILE_MB = float(os.getenv("MESSAGE_CACHE_MAX_FILE_MB", "25") or "25")
# Discord allows 10 files per message; one slot is reserved for the details file.
MAX_LOG_FILES = 9

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


def _message_text(content: str | None, limit: int = 3800) -> str:
    """Message content for a log card, keeping line breaks."""
    if not content:
        return "(без текста)"
    text = content.replace("@everyone", "@​everyone").replace(
        "@here", "@​here"
    )
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
    media: list[tuple[str, bool, bool]] | None = None,
) -> tuple[list[ui.Component], str | None]:
    """Build a Components V2 log card.

    ``media`` is a list of ``(filename, is_visual, spoiler)`` for files uploaded
    together with the card; images/videos are shown in a gallery, other files
    as file components.
    """
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
    if media:
        gallery_items = [
            disnake.MediaGalleryItem(f"attachment://{name}", spoiler=spoiler)
            for name, is_visual, spoiler in media
            if is_visual
        ]
        if gallery_items:
            components.append(
                ui.Separator(divider=True, spacing=disnake.SeparatorSpacing.small)
            )
            components.append(ui.MediaGallery(*gallery_items[:10]))
        for name, is_visual, spoiler in media:
            if not is_visual:
                components.append(ui.File(f"attachment://{name}", spoiler=spoiler))
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
        self._message_store: MessageStore | None = None
        self._message_store_tasks: dict[int, asyncio.Task] = {}
        # Last seen ``count`` of message deletion audit entries, keyed by
        # (guild_id, entry_id). Discord increments the count of an existing
        # entry instead of creating a new one for repeated deletions.
        self._message_audit_counts: dict[tuple[int, int], int] = {}
        self._message_audit_locks: dict[int, asyncio.Lock] = {}

    async def cog_load(self) -> None:
        try:
            self._message_store = MessageStore(MESSAGE_CACHE_DIR)
        except Exception:
            logger.exception(
                "Could not open message store in %s; deleted message content "
                "and attachments will not be preserved",
                MESSAGE_CACHE_DIR,
            )
        else:
            self._purge_message_store.start()
        if self.bot.is_ready():
            await self._initialize_audit_baseline()

    def cog_unload(self) -> None:
        self._purge_message_store.cancel()
        for task in self._message_store_tasks.values():
            task.cancel()
        if self._message_store is not None:
            self._message_store.close()

    @tasks.loop(hours=1)
    async def _purge_message_store(self) -> None:
        if self._message_store is None:
            return
        try:
            removed = await asyncio.to_thread(
                self._message_store.purge_older_than, MESSAGE_CACHE_DAYS
            )
        except Exception:
            logger.exception("Could not purge old messages from the message store")
            return
        if removed:
            logger.info("Removed %s expired messages from the message store", removed)

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
            # Message deletions are reported by the Gateway handlers, which add
            # the moderator from the audit log to the same card.
            disnake.AuditLogAction.message_delete,
            disnake.AuditLogAction.message_bulk_delete,
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

    # --- message storage --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message) -> None:
        if (
            self._message_store is None
            or message.guild is None
            or message.author.bot
            or self._is_log_channel(message.channel.id)
        ):
            return
        message_id = message.id
        task = asyncio.create_task(self._store_message(message))
        self._message_store_tasks[message_id] = task
        task.add_done_callback(
            lambda _: self._message_store_tasks.pop(message_id, None)
        )

    async def _store_message(self, message: disnake.Message) -> None:
        store = self._message_store
        if store is None or message.guild is None:
            return
        attachments = [
            StoredAttachment(
                id=attachment.id,
                filename=attachment.filename,
                content_type=attachment.content_type,
                size=attachment.size,
                url=attachment.url,
                spoiler=attachment.is_spoiler(),
            )
            for attachment in message.attachments
        ]
        stored = StoredMessage(
            message_id=message.id,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            author_name=str(message.author),
            content=message.content or "",
            created_at=message.created_at.timestamp(),
            attachments=attachments,
        )
        try:
            await asyncio.to_thread(store.save, stored)
            if not attachments:
                return
            max_bytes = int(MESSAGE_CACHE_MAX_FILE_MB * 1024 * 1024)
            for source, target in zip(message.attachments, attachments):
                if source.size > max_bytes:
                    target.skipped_reason = "слишком большой для сохранения"
                    continue
                try:
                    data = await source.read()
                except disnake.HTTPException as error:
                    target.skipped_reason = "не удалось скачать"
                    logger.warning(
                        "Could not download attachment %s of message %s: %s",
                        source.id,
                        message.id,
                        error,
                    )
                    continue
                target.path = await asyncio.to_thread(
                    store.write_attachment, message.id, target, data
                )
            await asyncio.to_thread(store.set_attachments, message.id, attachments)
        except Exception:
            logger.exception("Could not store message %s", message.id)

    async def _wait_for_stored(self, message_ids: list[int]) -> None:
        pending = [
            self._message_store_tasks[message_id]
            for message_id in message_ids
            if message_id in self._message_store_tasks
        ]
        if pending:
            await asyncio.wait(pending, timeout=60)

    async def _get_stored_message(self, message_id: int) -> StoredMessage | None:
        if self._message_store is None:
            return None
        await self._wait_for_stored([message_id])
        try:
            return await asyncio.to_thread(self._message_store.get, message_id)
        except Exception:
            logger.exception("Could not read message %s from the store", message_id)
            return None

    async def _get_stored_messages(self, message_ids: list[int]) -> list[StoredMessage]:
        if self._message_store is None:
            return []
        await self._wait_for_stored(message_ids)
        try:
            return await asyncio.to_thread(self._message_store.get_many, message_ids)
        except Exception:
            logger.exception("Could not read deleted messages from the store")
            return []

    async def _forget_messages(self, message_ids: list[int]) -> None:
        if self._message_store is None:
            return
        try:
            await asyncio.to_thread(self._message_store.delete, message_ids)
        except Exception:
            logger.exception("Could not remove messages from the store")

    @staticmethod
    def _message_from_cache(message: disnake.Message) -> StoredMessage:
        return StoredMessage(
            message_id=message.id,
            guild_id=message.guild.id if message.guild else 0,
            channel_id=message.channel.id,
            author_id=message.author.id,
            author_name=str(message.author),
            content=message.content or "",
            created_at=message.created_at.timestamp(),
            attachments=[
                StoredAttachment(
                    id=attachment.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=attachment.size,
                    url=attachment.url,
                    spoiler=attachment.is_spoiler(),
                )
                for attachment in message.attachments
            ],
        )

    @staticmethod
    def _format_stored_author(message: StoredMessage) -> str:
        name = message.author_name.replace("`", "ˋ")
        return f"<@{message.author_id}> (`{name}` · `{message.author_id}`)"

    async def _prepare_attachment_files(
        self,
        guild: disnake.Guild,
        attachments: list[StoredAttachment],
        *,
        max_files: int = MAX_LOG_FILES,
        prefix: str = "",
    ) -> tuple[list[disnake.File], list[tuple[str, bool, bool]], set[int]]:
        """Load stored attachment files so they can be re-uploaded to the log."""
        files: list[disnake.File] = []
        media: list[tuple[str, bool, bool]] = []
        uploaded: set[int] = set()
        size_limit = guild.filesize_limit
        for index, attachment in enumerate(attachments, start=1):
            if len(files) >= max_files:
                attachment.skipped_reason = (
                    attachment.skipped_reason or "не поместился в сообщение лога"
                )
                continue
            data = await asyncio.to_thread(MessageStore.read_attachment, attachment)
            if data is None and attachment.skipped_reason is None and attachment.url:
                # Last resort: Discord sometimes still serves the file shortly
                # after the message was deleted.
                try:
                    data = await self.bot.http.get_from_cdn(attachment.url)
                except disnake.HTTPException:
                    data = None
            if data is None:
                attachment.skipped_reason = attachment.skipped_reason or "файл не сохранён"
                continue
            if len(data) > size_limit:
                attachment.skipped_reason = "больше лимита загрузки сервера"
                continue
            name = f"{prefix}{index}_{safe_filename(attachment.filename)}"
            files.append(disnake.File(io.BytesIO(data), filename=name))
            media.append((name, attachment.is_image, attachment.spoiler))
            uploaded.add(attachment.id)
        return files, media, uploaded

    @staticmethod
    def _attachment_rows(
        attachments: list[StoredAttachment], uploaded: set[int], title: str
    ) -> str:
        lines = []
        for attachment in attachments:
            size_kb = max(attachment.size // 1024, 1)
            line = f"• `{attachment.filename.replace('`', 'ˋ')}` · {size_kb} КБ"
            if attachment.id in uploaded:
                line += " · сохранён ниже"
            elif attachment.skipped_reason:
                line += f" · {attachment.skipped_reason}"
            lines.append(line)
        return f"**{title} ({len(attachments)})**\n" + "\n".join(lines)

    # --- message events ---------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: disnake.RawMessageUpdateEvent) -> None:
        data = payload.data
        if (
            payload.guild_id is None
            or self._is_log_channel(payload.channel_id)
            or ("content" not in data and "attachments" not in data)
        ):
            return
        # Embed unfurls and other system updates do not set edited_timestamp.
        if "edited_timestamp" in data and not data["edited_timestamp"]:
            return

        before = payload.cached_message
        author_data = data.get("author") or {}
        if (before is not None and before.author.bot) or author_data.get("bot"):
            return

        stored = await self._get_stored_message(payload.message_id)
        if stored is None and before is not None:
            stored = self._message_from_cache(before)

        before_content = stored.content if stored is not None else None
        after_content = data.get("content", before_content)
        content_changed = "content" in data and before_content != after_content

        removed: list[StoredAttachment] = []
        if "attachments" in data and stored is not None:
            current_ids = {int(item["id"]) for item in data["attachments"]}
            removed = [a for a in stored.attachments if a.id not in current_ids]

        if not content_changed and not removed:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if before is not None:
            author = _safe_text(before.author)
        elif stored is not None:
            author = self._format_stored_author(stored)
        elif author_data.get("id"):
            author = f"<@{author_data['id']}> (`{author_data['id']}`)"
        else:
            author = "Не определён"
        message_url = (
            f"https://discord.com/channels/{payload.guild_id}/"
            f"{payload.channel_id}/{payload.message_id}"
        )

        details = [
            f"**Автор** · {author}",
            f"**Канал** · {_safe_text(channel or f'ID {payload.channel_id}')}",
        ]
        if content_changed:
            details.append(
                "**Было**\n"
                + (
                    _message_text(before_content)
                    if before_content is not None
                    else "(не было сохранено)"
                )
            )
            details.append(f"**Стало**\n{_message_text(after_content)}")

        files: list[disnake.File] = []
        media: list[tuple[str, bool, bool]] = []
        if removed:
            files, media, uploaded = await self._prepare_attachment_files(guild, removed)
            details.append(self._attachment_rows(removed, uploaded, "Удалены вложения"))
        details.extend(
            (
                f"**Ссылка** · [Открыть сообщение]({message_url})",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            )
        )
        await self._send_log(
            guild,
            "Изменение сообщения",
            details,
            log_key="message_edit",
            files=files,
            media=media,
        )

        if self._message_store is not None and stored is not None:
            try:
                if content_changed:
                    await asyncio.to_thread(
                        self._message_store.update_content,
                        payload.message_id,
                        after_content or "",
                    )
                if removed:
                    removed_ids = {a.id for a in removed}
                    await asyncio.to_thread(
                        self._message_store.set_attachments,
                        payload.message_id,
                        [a for a in stored.attachments if a.id not in removed_ids],
                    )
                    await asyncio.to_thread(
                        self._message_store.remove_attachment_files, removed
                    )
            except Exception:
                logger.exception(
                    "Could not update stored message %s", payload.message_id
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

        stored = await self._get_stored_message(payload.message_id)
        if stored is None and cached is not None:
            stored = self._message_from_cache(cached)

        if cached is not None:
            author = _safe_text(cached.author)
        elif stored is not None:
            author = self._format_stored_author(stored)
        else:
            author = "Не определён"
        author_id = stored.author_id if stored is not None else None
        initiator = await self._find_message_delete_initiator(
            guild, payload.channel_id, author_id
        )
        channel = self.bot.get_channel(payload.channel_id)
        details = [
            f"**Автор** · {author}",
            f"**Канал** · {_safe_text(channel or f'ID {payload.channel_id}')}",
        ]

        files: list[disnake.File] = []
        media: list[tuple[str, bool, bool]] = []
        if stored is None:
            details.append(
                "**Сообщение** · Не сохранено: отправлено до запуска бота "
                "или старше срока хранения"
            )
        else:
            details.append(f"**Сообщение**\n{_message_text(stored.content)}")
            details.append(f"**Отправлено** · <t:{int(stored.created_at)}:f>")
            if stored.attachments:
                files, media, uploaded = await self._prepare_attachment_files(
                    guild, stored.attachments
                )
                details.append(
                    self._attachment_rows(stored.attachments, uploaded, "Вложения")
                )
        details.extend(
            (
                f"**Удалил** · {initiator}",
                f"**ID сообщения** · `{payload.message_id}`",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            )
        )
        await self._send_log(
            guild,
            "Удаление сообщения",
            details,
            log_key="message_delete",
            files=files,
            media=media,
        )
        await self._forget_messages([payload.message_id])

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(
        self, payload: disnake.RawBulkMessageDeleteEvent
    ) -> None:
        if payload.guild_id is None or self._is_log_channel(payload.channel_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        message_ids = sorted(payload.message_ids)
        messages = {
            message.message_id: message
            for message in await self._get_stored_messages(message_ids)
        }
        for cached in payload.cached_messages:
            if cached.id not in messages and not cached.author.bot:
                messages[cached.id] = self._message_from_cache(cached)
        ordered = sorted(messages.values(), key=lambda message: message.created_at)

        channel = self.bot.get_channel(payload.channel_id)
        details = [
            f"**Канал** · {_safe_text(channel or f'ID {payload.channel_id}')}",
            f"**Количество** · {len(message_ids)}",
            f"**Сохранено** · {len(ordered)} из {len(message_ids)}",
        ]

        files: list[disnake.File] = []
        media: list[tuple[str, bool, bool]] = []
        if ordered:
            all_attachments = [a for message in ordered for a in message.attachments]
            # One slot is used by the transcript file.
            files, media, uploaded = await self._prepare_attachment_files(
                guild, all_attachments, max_files=MAX_LOG_FILES - 1
            )
            transcript_lines = []
            for message in ordered:
                sent_at = datetime.datetime.fromtimestamp(message.created_at).strftime(
                    "%d.%m.%Y %H:%M:%S"
                )
                transcript_lines.append(
                    f"[{sent_at}] {message.author_name} ({message.author_id}):"
                )
                transcript_lines.append(message.content or "(без текста)")
                for attachment in message.attachments:
                    status = (
                        "сохранён в логе"
                        if attachment.id in uploaded
                        else attachment.skipped_reason or "файл не сохранён"
                    )
                    transcript_lines.append(
                        f"  [вложение] {attachment.filename} "
                        f"({attachment.size} байт, {status}) {attachment.url}"
                    )
                transcript_lines.append("")
            transcript_name = "deleted-messages.txt"
            files.insert(
                0,
                disnake.File(
                    io.BytesIO("\n".join(transcript_lines).encode("utf-8")),
                    filename=transcript_name,
                ),
            )
            media.insert(0, (transcript_name, False, False))
            details.append(
                "**Содержимое** · Текст удалённых сообщений приложен файлом "
                f"`{transcript_name}`"
            )
            if all_attachments:
                details.append(
                    self._attachment_rows(all_attachments, uploaded, "Вложения")
                )
        details.extend(
            (
                f"**Удалил** · {await self._find_bulk_delete_initiator(guild, payload.channel_id)}",
                f"**Время** · <t:{int(disnake.utils.utcnow().timestamp())}:F>",
            )
        )
        await self._send_log(
            guild,
            "Массовое удаление сообщений",
            details,
            log_key="message_bulk_delete",
            files=files,
            media=media,
        )
        await self._forget_messages(message_ids)

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
                    "Audit attribution (voice, message deletions) is unavailable in guild %s: "
                    "the bot is missing VIEW_AUDIT_LOG",
                    guild.id,
                )
                self._audit_permission_warnings.add(guild.id)
            return None

        try:
            return [entry async for entry in guild.audit_logs(limit=50)]
        except disnake.Forbidden:
            logger.warning(
                "Could not read audit log for guild %s: Discord returned 403",
                guild.id,
            )
        except disnake.HTTPException:
            logger.exception(
                "Failed to fetch audit log for guild %s", guild.id
            )
        return None

    async def _find_message_delete_initiator(
        self, guild: disnake.Guild, channel_id: int, author_id: int | None
    ) -> str:
        def match(entries: list[disnake.AuditLogEntry]) -> disnake.AuditLogEntry | None:
            return self._match_message_delete_entry(
                guild.id, entries, channel_id, author_id
            )

        return await self._find_delete_initiator(
            guild,
            match,
            not_found="Сам автор (в журнале аудита нет записи об удалении)",
        )

    async def _find_bulk_delete_initiator(
        self, guild: disnake.Guild, channel_id: int
    ) -> str:
        def match(entries: list[disnake.AuditLogEntry]) -> disnake.AuditLogEntry | None:
            now = disnake.utils.utcnow()
            for entry in entries:
                key = (guild.id, entry.id)
                if (
                    entry.action != disnake.AuditLogAction.message_bulk_delete
                    or key in self._message_audit_counts
                    or getattr(entry.target, "id", None) != channel_id
                    or (now - entry.created_at).total_seconds() > 120
                ):
                    continue
                self._message_audit_counts[key] = 1
                return entry
            return None

        return await self._find_delete_initiator(
            guild, match, not_found="Не определён (в журнале аудита нет записи)"
        )

    async def _find_delete_initiator(
        self,
        guild: disnake.Guild,
        match: Any,
        *,
        not_found: str,
    ) -> str:
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.view_audit_log:
            return "Нет доступа к журналу аудита"
        await self._voice_audit_baseline_ready.wait()
        lock = self._message_audit_locks.setdefault(guild.id, asyncio.Lock())
        # Discord writes the audit entry slightly after the Gateway event.
        for delay in (1.0, 1.5):
            await asyncio.sleep(delay)
            async with lock:
                entries = await self._fetch_voice_audit_entries(guild)
                if entries is None:
                    return "Не удалось прочитать журнал аудита"
                entry = match(entries)
            if entry is not None:
                text = _safe_text(entry.user) if entry.user else "Не определён"
                if entry.reason:
                    text += f"\n**Причина** · {_safe_text(entry.reason)}"
                return text
        return not_found

    def _match_message_delete_entry(
        self,
        guild_id: int,
        entries: list[disnake.AuditLogEntry],
        channel_id: int,
        author_id: int | None,
    ) -> disnake.AuditLogEntry | None:
        baselined = guild_id in self._voice_audit_baselined
        now = disnake.utils.utcnow()
        candidates: list[tuple[disnake.AuditLogEntry, tuple[int, int], int]] = []
        for entry in entries:
            if entry.action != disnake.AuditLogAction.message_delete:
                continue
            if getattr(getattr(entry.extra, "channel", None), "id", None) != channel_id:
                continue
            target_id = getattr(entry.target, "id", None)
            if author_id is not None and target_id is not None and target_id != author_id:
                continue
            count = max(1, int(getattr(entry.extra, "count", 1) or 1))
            key = (guild_id, entry.id)
            previous = self._message_audit_counts.get(key)
            if previous is None:
                recent = (now - entry.created_at).total_seconds() < 60
                previous = 0 if baselined or recent else count
            if count > previous:
                candidates.append((entry, key, previous))
        # Without a known author several moderators could match; do not guess.
        if not candidates or (author_id is None and len(candidates) > 1):
            return None
        entry, key, previous = candidates[0]
        self._message_audit_counts[key] = previous + 1
        return entry

    async def _prime_voice_audit_counts(self, guild: disnake.Guild) -> None:
        entries = await self._fetch_voice_audit_entries(guild)
        if entries is None:
            return
        now = disnake.utils.utcnow()
        for entry in entries:
            if entry.action in (
                disnake.AuditLogAction.message_delete,
                disnake.AuditLogAction.message_bulk_delete,
            ):
                self._message_audit_counts[(guild.id, entry.id)] = max(
                    1, int(getattr(entry.extra, "count", 1) or 1)
                )
                continue
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
    ) -> bool:
        """Send a log card; returns ``False`` if Discord rejected the upload."""
        channel, channel_id = await self._get_log_channel(log_key)
        if channel is None:
            return True
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
            return False
        return True

    async def _send_log(
        self,
        guild: disnake.Guild,
        title: str,
        details: list[str],
        *,
        log_key: str = "default",
        files: list[disnake.File] | None = None,
        media: list[tuple[str, bool, bool]] | None = None,
    ) -> None:
        emoji_name = LOG_EMOJI_NAMES.get(log_key)
        if emoji_name and emoji_name not in self._application_emojis:
            await self._refresh_application_emojis()
        components, overflow_text = _build_log_components(
            guild, title, details, log_key, self._application_emojis, media
        )
        all_files: list[disnake.File] = []
        if overflow_text is not None:
            all_files.append(
                disnake.File(
                    io.BytesIO(overflow_text.encode("utf-8")),
                    filename="server-log-details.txt",
                )
            )
        all_files.extend(files or [])
        sent = await self._send_components(
            guild,
            components,
            log_key=log_key,
            context=f"server log '{title}'",
            files=all_files or None,
        )
        if not sent and files:
            # Most often the attachments together exceed the upload limit:
            # keep the log itself and drop the files.
            logger.warning(
                "Retrying server log '%s' for guild %s without attachments",
                title,
                guild.id,
            )
            await self._send_log(
                guild,
                title,
                [*details, "**Файлы** · Не удалось загрузить в канал логов"],
                log_key=log_key,
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(ServerLogsCog(bot))
