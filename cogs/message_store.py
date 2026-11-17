"""Persistent storage of guild messages and their attachments.

Discord removes attachments from its CDN shortly after a message is deleted and
the gateway cache of disnake is lost on restart, so the bot keeps its own copy
of every message (text, author and attachment files) for a limited time.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    attachments TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_created_at ON messages (created_at);
"""


@dataclass
class StoredAttachment:
    id: int
    filename: str
    content_type: str | None
    size: int
    url: str
    spoiler: bool = False
    path: str | None = None
    skipped_reason: str | None = None

    @property
    def is_image(self) -> bool:
        if self.content_type:
            return self.content_type.startswith(("image/", "video/"))
        return self.filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm", ".mov")
        )


@dataclass
class StoredMessage:
    message_id: int
    guild_id: int
    channel_id: int
    author_id: int
    author_name: str
    content: str
    created_at: float
    attachments: list[StoredAttachment] = field(default_factory=list)


def safe_filename(name: str, fallback: str = "file") -> str:
    """Return an ASCII filename usable in ``attachment://`` references."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")[:60] or fallback
    ext = re.sub(r"[^A-Za-z0-9]+", "", ext)[:10]
    return f"{stem}.{ext}" if ext else stem


class MessageStore:
    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self.directory = Path(directory)
        self.files_directory = self.directory / "attachments"
        self.files_directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(
            self.directory / "messages.sqlite3", check_same_thread=False
        )
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- attachments -----------------------------------------------------

    def attachment_path(self, message_id: int, attachment: StoredAttachment) -> Path:
        return (
            self.files_directory
            / str(message_id)
            / f"{attachment.id}_{safe_filename(attachment.filename)}"
        )

    def write_attachment(
        self, message_id: int, attachment: StoredAttachment, data: bytes
    ) -> str:
        path = self.attachment_path(message_id, attachment)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    @staticmethod
    def read_attachment(attachment: StoredAttachment) -> bytes | None:
        if not attachment.path:
            return None
        try:
            return Path(attachment.path).read_bytes()
        except OSError:
            return None

    def _remove_files(self, message_id: int) -> None:
        shutil.rmtree(self.files_directory / str(message_id), ignore_errors=True)

    def remove_attachment_files(self, attachments: list[StoredAttachment]) -> None:
        for attachment in attachments:
            if attachment.path:
                try:
                    Path(attachment.path).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove stored file %s", attachment.path)

    # --- messages --------------------------------------------------------

    def save(self, message: StoredMessage) -> None:
        payload = json.dumps(
            [attachment.__dict__ for attachment in message.attachments],
            ensure_ascii=False,
        )
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message.message_id,
                    message.guild_id,
                    message.channel_id,
                    message.author_id,
                    message.author_name,
                    message.content,
                    message.created_at,
                    payload,
                ),
            )
            self._db.commit()

    def get(self, message_id: int) -> StoredMessage | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def get_many(self, message_ids: list[int]) -> list[StoredMessage]:
        if not message_ids:
            return []
        result: list[StoredMessage] = []
        with self._lock:
            for start in range(0, len(message_ids), 500):
                chunk = message_ids[start : start + 500]
                placeholders = ",".join("?" * len(chunk))
                rows = self._db.execute(
                    f"SELECT * FROM messages WHERE message_id IN ({placeholders})",
                    chunk,
                ).fetchall()
                result.extend(self._from_row(row) for row in rows)
        result.sort(key=lambda message: message.created_at)
        return result

    def update_content(self, message_id: int, content: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE messages SET content = ? WHERE message_id = ?",
                (content, message_id),
            )
            self._db.commit()

    def set_attachments(
        self, message_id: int, attachments: list[StoredAttachment]
    ) -> None:
        payload = json.dumps(
            [attachment.__dict__ for attachment in attachments], ensure_ascii=False
        )
        with self._lock:
            self._db.execute(
                "UPDATE messages SET attachments = ? WHERE message_id = ?",
                (payload, message_id),
            )
            self._db.commit()

    def delete(self, message_ids: list[int]) -> None:
        if not message_ids:
            return
        with self._lock:
            self._db.executemany(
                "DELETE FROM messages WHERE message_id = ?",
                [(message_id,) for message_id in message_ids],
            )
            self._db.commit()
        for message_id in message_ids:
            self._remove_files(message_id)

    def purge_older_than(self, days: float) -> int:
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days)
        ).timestamp()
        with self._lock:
            ids = [
                row[0]
                for row in self._db.execute(
                    "SELECT message_id FROM messages WHERE created_at < ?", (cutoff,)
                )
            ]
        self.delete(ids)
        # Remove orphaned attachment folders (e.g. after a crash mid-download).
        with self._lock:
            known = {
                str(row[0]) for row in self._db.execute("SELECT message_id FROM messages")
            }
        for folder in self.files_directory.iterdir():
            if folder.is_dir() and folder.name not in known:
                shutil.rmtree(folder, ignore_errors=True)
        return len(ids)

    @staticmethod
    def _from_row(row: tuple) -> StoredMessage:
        attachments = [
            StoredAttachment(**item) for item in json.loads(row[7] or "[]")
        ]
        return StoredMessage(
            message_id=row[0],
            guild_id=row[1],
            channel_id=row[2],
            author_id=row[3],
            author_name=row[4],
            content=row[5],
            created_at=row[6],
            attachments=attachments,
        )
