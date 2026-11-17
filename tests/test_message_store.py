import asyncio
import datetime
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import disnake

from cogs.message_store import (
    MessageStore,
    StoredAttachment,
    StoredMessage,
    safe_filename,
)
from cogs.server_logs import ServerLogsCog, _build_log_components


def _stored_message(message_id: int = 1, created_at: float | None = None) -> StoredMessage:
    return StoredMessage(
        message_id=message_id,
        guild_id=10,
        channel_id=20,
        author_id=30,
        author_name="user",
        content="hello\nworld",
        created_at=created_at
        if created_at is not None
        else datetime.datetime.now(datetime.timezone.utc).timestamp(),
        attachments=[
            StoredAttachment(
                id=100,
                filename="cat photo.png",
                content_type="image/png",
                size=4,
                url="https://cdn.example/cat.png",
            ),
            StoredAttachment(
                id=101,
                filename="notes.txt",
                content_type="text/plain",
                size=5,
                url="https://cdn.example/notes.txt",
            ),
        ],
    )


class MessageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MessageStore(self.tmp.name)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_message_and_files_round_trip(self) -> None:
        message = _stored_message()
        self.store.save(message)
        message.attachments[0].path = self.store.write_attachment(
            1, message.attachments[0], b"\x89PNG"
        )
        self.store.set_attachments(1, message.attachments)

        loaded = self.store.get(1)

        self.assertEqual(loaded.content, "hello\nworld")
        self.assertEqual(MessageStore.read_attachment(loaded.attachments[0]), b"\x89PNG")
        self.assertIsNone(MessageStore.read_attachment(loaded.attachments[1]))

    def test_delete_removes_record_and_files(self) -> None:
        message = _stored_message()
        self.store.save(message)
        path = self.store.write_attachment(1, message.attachments[0], b"data")

        self.store.delete([1])

        self.assertIsNone(self.store.get(1))
        self.assertIsNone(
            MessageStore.read_attachment(
                StoredAttachment(1, "a", None, 1, "", path=path)
            )
        )

    def test_purge_removes_only_expired_messages(self) -> None:
        old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
        self.store.save(_stored_message(1, old.timestamp()))
        self.store.save(_stored_message(2))

        self.assertEqual(self.store.purge_older_than(14), 1)
        self.assertIsNone(self.store.get(1))
        self.assertIsNotNone(self.store.get(2))

    def test_safe_filename_is_ascii(self) -> None:
        self.assertEqual(safe_filename("фото кота.PNG"), "file.PNG")
        self.assertEqual(safe_filename("cat photo.png"), "cat_photo.png")


class DeletedMessageLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.bot = MagicMock()
        self.bot.http.get_from_cdn = AsyncMock(side_effect=disnake.HTTPException(MagicMock(status=404), "gone"))
        self.guild = MagicMock(id=10, filesize_limit=10 * 1024 * 1024)
        self.guild.name = "Test"
        self.bot.get_guild.return_value = self.guild
        self.bot.get_channel.return_value = None
        self.cog = ServerLogsCog(self.bot)
        self.cog._message_store = MessageStore(self.tmp.name)

    def tearDown(self) -> None:
        self.cog._message_store.close()
        self.tmp.cleanup()

    def test_deleted_message_reuploads_stored_attachments(self) -> None:
        store = self.cog._message_store
        message = _stored_message()
        store.save(message)
        message.attachments[0].path = store.write_attachment(
            1, message.attachments[0], b"\x89PNG"
        )
        store.set_attachments(1, message.attachments)

        payload = MagicMock(
            guild_id=10, channel_id=20, message_id=1, cached_message=None
        )
        with patch.object(self.cog, "_send_log", new=AsyncMock()) as send_log, patch.object(
            self.cog,
            "_find_message_delete_initiator",
            new=AsyncMock(return_value="<@40> (`mod` · `40`)"),
        ) as find_initiator:
            asyncio.run(self.cog.on_raw_message_delete(payload))

        find_initiator.assert_awaited_once_with(self.guild, 20, 30)

        send_log.assert_awaited_once()
        details = send_log.await_args.args[2]
        kwargs = send_log.await_args.kwargs
        text = "\n".join(details)
        self.assertIn("hello\nworld", text)
        self.assertIn("<@30>", text)
        self.assertIn("`cat photo.png` · 1 КБ · сохранён ниже", text)
        self.assertIn("`notes.txt` · 1 КБ · файл не сохранён", text)
        self.assertEqual([f.filename for f in kwargs["files"]], ["1_cat_photo.png"])
        self.assertEqual(kwargs["media"], [("1_cat_photo.png", True, False)])
        self.assertIn("**Удалил** · <@40> (`mod` · `40`)", text)
        self.assertNotIn("Ссылка", text)
        self.assertIsNone(store.get(1))

    def test_edit_logs_removed_attachment(self) -> None:
        store = self.cog._message_store
        message = _stored_message()
        store.save(message)
        message.attachments[1].path = store.write_attachment(
            1, message.attachments[1], b"notes"
        )
        store.set_attachments(1, message.attachments)

        payload = MagicMock(
            guild_id=10,
            channel_id=20,
            message_id=1,
            cached_message=None,
            data={
                "content": "hello\nworld",
                "edited_timestamp": "2026-11-17T00:00:00+00:00",
                "attachments": [{"id": "100"}],
                "author": {"id": "30"},
            },
        )
        with patch.object(self.cog, "_send_log", new=AsyncMock()) as send_log:
            asyncio.run(self.cog.on_raw_message_edit(payload))

        text = "\n".join(send_log.await_args.args[2])
        self.assertIn("Удалены вложения (1)", text)
        self.assertNotIn("**Было**", text)
        self.assertEqual(
            [f.filename for f in send_log.await_args.kwargs["files"]], ["1_notes.txt"]
        )
        self.assertEqual([a.id for a in store.get(1).attachments], [100])

    def test_media_components_reference_uploaded_files(self) -> None:
        components, _ = _build_log_components(
            self.guild,
            "Удаление сообщения",
            ["**Автор** · <@1>"],
            "message_delete",
            media=[("1_a.png", True, False), ("2_b.txt", False, False)],
        )
        gallery = [c for c in components if isinstance(c, disnake.ui.MediaGallery)]
        files = [c for c in components if isinstance(c, disnake.ui.File)]
        self.assertEqual(gallery[0].items[0].media.url, "attachment://1_a.png")
        self.assertEqual(files[0].file.url, "attachment://2_b.txt")


def _audit_entry(entry_id, action, *, count=1, channel_id=20, target_id=30, age=0):
    entry = MagicMock(id=entry_id, action=action, reason=None)
    entry.extra = MagicMock(count=count, channel=MagicMock(id=channel_id))
    entry.target = MagicMock(id=target_id)
    entry.created_at = disnake.utils.utcnow() - datetime.timedelta(seconds=age)
    return entry


class MessageDeleteAuditMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cog = ServerLogsCog(MagicMock())
        self.cog._voice_audit_baselined.add(10)

    def test_new_entry_matches_author_and_channel(self) -> None:
        entry = _audit_entry(1, disnake.AuditLogAction.message_delete)
        other = _audit_entry(2, disnake.AuditLogAction.message_delete, target_id=99)

        self.assertIs(
            self.cog._match_message_delete_entry(10, [other, entry], 20, 30), entry
        )

    def test_aggregated_entry_matches_only_new_increments(self) -> None:
        self.cog._message_audit_counts[(10, 1)] = 3
        entry = _audit_entry(1, disnake.AuditLogAction.message_delete, count=3, age=200)

        self.assertIsNone(self.cog._match_message_delete_entry(10, [entry], 20, 30))

        entry.extra.count = 4
        self.assertIs(self.cog._match_message_delete_entry(10, [entry], 20, 30), entry)
        self.assertIsNone(self.cog._match_message_delete_entry(10, [entry], 20, 30))

    def test_entry_in_other_channel_is_ignored(self) -> None:
        entry = _audit_entry(1, disnake.AuditLogAction.message_delete, channel_id=21)

        self.assertIsNone(self.cog._match_message_delete_entry(10, [entry], 20, 30))

    def test_audit_card_for_message_delete_is_not_sent(self) -> None:
        entry = _audit_entry(1, disnake.AuditLogAction.message_delete)
        with patch.object(self.cog, "_send_log", new=AsyncMock()) as send_log:
            asyncio.run(self.cog.on_audit_log_entry_create(entry))
        send_log.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
