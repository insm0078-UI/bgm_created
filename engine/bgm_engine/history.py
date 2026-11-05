"""SQLite record of every generated track (prompt, settings, model versions, date)."""

import json
import os
import sqlite3
import threading
from dataclasses import asdict
from typing import Any

from bgm_engine.jobs import GenerateRequest

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    duration REAL,
    caption TEXT,
    seed INTEGER,
    bpm INTEGER,
    keyscale TEXT,
    dit_model TEXT,
    lm_model TEXT,
    request_json TEXT NOT NULL
)
"""
_COLUMNS = ["id", "path", "created_at", "duration", "caption", "seed", "bpm", "keyscale",
            "dit_model", "lm_model", "kind", "parent_id"]
# Columns added after the first release; created on open for older databases.
_MIGRATIONS = {"kind": "TEXT NOT NULL DEFAULT 'generated'", "parent_id": "TEXT"}
KINDS = ("generated", "variation", "loop")


class HistoryStore:
    """Thread-safe persistent list of generated tracks."""

    def __init__(self, db_path: str):
        """Open (and create if needed) the history database at ``db_path``."""
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute(_SCHEMA)
            existing = {row[1] for row in self._conn.execute("PRAGMA table_info(tracks)")}
            for column, ddl in _MIGRATIONS.items():
                if column not in existing:
                    self._conn.execute(f"ALTER TABLE tracks ADD COLUMN {column} {ddl}")

    def add_many(self, request: GenerateRequest | dict[str, Any], results: list[dict[str, Any]],
                 kind: str = "generated", parent_id: str | None = None) -> None:
        """Record results from one job.

        Args:
            request: The originating request (derived tracks pass their parent's request).
            results: Track dicts from the runtime.
            kind: One of ``KINDS``.
            parent_id: Source track for variations and loops.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown kind: {kind}")
        req = request if isinstance(request, dict) else asdict(request)
        request_json = json.dumps(req, ensure_ascii=False)
        rows = [tuple({**r, "kind": kind, "parent_id": parent_id}.get(c) for c in _COLUMNS)
                + (request_json,) for r in results if r.get("id")]
        with self._lock, self._conn:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO tracks ({', '.join(_COLUMNS)}, request_json) "
                f"VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})",
                rows,
            )

    def list(self, limit: int = 300) -> list[dict[str, Any]]:
        """Return the newest tracks first, flagging files that no longer exist."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tracks ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._to_dict(row) for row in rows]

    def get(self, track_id: str) -> dict[str, Any] | None:
        """Return one track by id, or None."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return self._to_dict(row) if row else None

    def delete(self, track_id: str) -> dict[str, Any] | None:
        """Remove a track record and return it (None if unknown). Files are left to the caller."""
        with self._lock, self._conn:
            row = self._conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = {c: row[c] for c in _COLUMNS}
        item["request"] = json.loads(row["request_json"])
        item["exists"] = os.path.isfile(row["path"])
        return item
