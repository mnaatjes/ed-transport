"""SQLite-backed circular FIFO request spool storage adapter."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

from ....core.domain.exceptions import (
    SpoolCapacityExceededError,
    SpoolStorageCorruptError,
)
from ....core.ports.driven.spool_storage_port import SpoolStoragePort
from ....core.ports.dto.transport_dto import HttpRequestDTO, SpoolRecordDTO

_logger = logging.getLogger(__name__)


class SqliteSpoolStorageAdapter(SpoolStoragePort):
    """Thread-safe persistent SQLite FIFO circular queue with WAL mode and corrupt handling."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS spool_records (
        sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        correlation_id TEXT NOT NULL,
        url TEXT NOT NULL,
        method TEXT NOT NULL,
        headers_json TEXT NOT NULL,
        body BLOB NOT NULL,
        timeout REAL NOT NULL,
        created_at REAL NOT NULL,
        retry_count INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_spool_created ON spool_records(created_at);
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        max_capacity_bytes: int = 50 * 1024 * 1024,
        overflow_strategy: str = "drop_oldest",
        auto_recover_corrupt: bool = False,
    ) -> None:
        self._db_path = db_path
        self._max_capacity_bytes = max_capacity_bytes
        self._overflow_strategy = overflow_strategy
        self._auto_recover = auto_recover_corrupt
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initializes database schema with WAL mode and busy timeout."""
        with self._lock:
            try:
                if self._db_path != ":memory:":
                    Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

                self._conn = sqlite3.connect(
                    self._db_path,
                    timeout=5.0,
                    check_same_thread=False,
                )
                self._conn.row_factory = sqlite3.Row
                # Configure WAL mode & busy timeout
                if self._db_path != ":memory:":
                    self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA busy_timeout=5000;")
                self._conn.executescript(self.SCHEMA)
                self._conn.commit()

            except sqlite3.DatabaseError as err:
                if self._conn:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
                if self._auto_recover and self._db_path != ":memory:":
                    _logger.critical(
                        "Spool database corrupted at %s; recovering (%s)", self._db_path, err
                    )
                    self._recover_corrupt_database(err)
                else:
                    raise SpoolStorageCorruptError(
                        storage_path=self._db_path,
                        details=str(err),
                    ) from err

    def _recover_corrupt_database(self, err: Exception) -> None:
        """Quarantines corrupt database file and recreates fresh schema."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

        timestamp = int(time.time())
        quarantine_path = f"{self._db_path}.corrupt.{timestamp}"
        try:
            if os.path.exists(self._db_path):
                os.rename(self._db_path, quarantine_path)
            for suffix in ("-wal", "-shm"):
                wal_file = f"{self._db_path}{suffix}"
                if os.path.exists(wal_file):
                    os.rename(wal_file, f"{quarantine_path}{suffix}")
        except OSError as rename_err:
            _logger.critical("Failed to quarantine corrupt db: %s", rename_err)

        # Retry initialization
        self._conn = sqlite3.connect(
            self._db_path,
            timeout=5.0,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def push(self, record: SpoolRecordDTO) -> None:
        """Appends a request to the queue in FIFO order, enforcing capacity constraints."""
        with self._lock:
            conn = self._get_connection()
            body_bytes = record.request.body or b""
            body_size = len(body_bytes)

            current_size = self.size_bytes()
            if current_size + body_size > self._max_capacity_bytes:
                if self._overflow_strategy == "reject":
                    raise SpoolCapacityExceededError(
                        current_depth=self.count(),
                        capacity_ceiling=self._max_capacity_bytes,
                    )
                # Drop oldest
                while current_size + body_size > self._max_capacity_bytes:
                    oldest = self.peek()
                    if oldest is None:
                        break
                    self.pop()
                    current_size = self.size_bytes()

            headers_json = json.dumps(dict(record.request.headers))
            conn.execute(
                """
                INSERT INTO spool_records (
                    correlation_id, url, method, headers_json,
                    body, timeout, created_at, retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    record.request.url,
                    record.request.method,
                    headers_json,
                    body_bytes,
                    record.request.timeout,
                    record.created_at,
                    record.retry_count,
                ),
            )
            conn.commit()

    def pop(self) -> SpoolRecordDTO | None:
        """Dequeues and returns the oldest record."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM spool_records ORDER BY sequence_id ASC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None

            seq_id = row["sequence_id"]
            conn.execute("DELETE FROM spool_records WHERE sequence_id = ?", (seq_id,))
            conn.commit()
            return self._row_to_dto(row)

    def peek(self) -> SpoolRecordDTO | None:
        """Peeks at the oldest record without dequeuing."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT * FROM spool_records ORDER BY sequence_id ASC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dto(row)

    def count(self) -> int:
        """Returns total records stored."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT COUNT(*) FROM spool_records")
            row = cursor.fetchone()
            return row[0] if row else 0

    def size_bytes(self) -> int:
        """Returns aggregate byte size of stored request bodies."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT TOTAL(LENGTH(body)) FROM spool_records")
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else 0

    def clear(self) -> None:
        """Deletes all enqueued records."""
        with self._lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM spool_records")
            conn.commit()

    def close(self) -> None:
        """Closes the underlying database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        assert self._conn is not None
        return self._conn

    def _row_to_dto(self, row: sqlite3.Row) -> SpoolRecordDTO:
        headers_dict = json.loads(row["headers_json"])
        req = HttpRequestDTO(
            url=row["url"],
            method=row["method"],
            headers=headers_dict,
            body=row["body"],
            timeout=row["timeout"],
        )
        return SpoolRecordDTO(
            sequence_id=row["sequence_id"],
            request=req,
            created_at=row["created_at"],
            retry_count=row["retry_count"],
        )
