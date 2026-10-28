"""Unit tests for MemorySpoolStorageAdapter and SqliteSpoolStorageAdapter."""

from __future__ import annotations

import pytest

from ed_transport.adapters.driven.spool.memory_spool import MemorySpoolStorageAdapter
from ed_transport.adapters.driven.spool.sqlite_spool import SqliteSpoolStorageAdapter
from ed_transport.core.domain.exceptions import (
    SpoolCapacityExceededError,
    SpoolStorageCorruptError,
)
from ed_transport.core.ports.dto.transport_dto import HttpRequestDTO, SpoolRecordDTO


def _make_record(seq: int = 1, body: bytes = b"payload") -> SpoolRecordDTO:
    req = HttpRequestDTO(url="https://api.ed.test/events", method="POST", body=body)
    return SpoolRecordDTO(sequence_id=seq, request=req, created_at=1000.0, retry_count=0)


def test_memory_spool_fifo_order() -> None:
    spool = MemorySpoolStorageAdapter(max_capacity=5)
    rec1 = _make_record(1, b"first")
    rec2 = _make_record(2, b"second")

    spool.push(rec1)
    spool.push(rec2)
    assert spool.count() == 2
    assert spool.peek().request.body == b"first"

    popped1 = spool.pop()
    assert popped1.request.body == b"first"
    assert spool.count() == 1

    popped2 = spool.pop()
    assert popped2.request.body == b"second"
    assert spool.count() == 0
    assert spool.pop() is None


def test_memory_spool_eviction_drop_oldest() -> None:
    spool = MemorySpoolStorageAdapter(max_capacity=2, eviction_policy="DropOldest")
    spool.push(_make_record(1, b"rec1"))
    spool.push(_make_record(2, b"rec2"))
    spool.push(_make_record(3, b"rec3"))  # Should drop rec1

    assert spool.count() == 2
    assert spool.pop().request.body == b"rec2"
    assert spool.pop().request.body == b"rec3"


def test_memory_spool_reject_newest() -> None:
    spool = MemorySpoolStorageAdapter(max_capacity=1, eviction_policy="RejectNewest")
    spool.push(_make_record(1, b"rec1"))

    with pytest.raises(SpoolCapacityExceededError):
        spool.push(_make_record(2, b"rec2"))


def test_sqlite_spool_fifo_persistence(tmp_path: pytest.TempPathFactory) -> None:
    db_file = str(tmp_path / "test_spool.db")
    spool = SqliteSpoolStorageAdapter(db_path=db_file)

    rec1 = _make_record(1, b"sqlite_1")
    rec2 = _make_record(2, b"sqlite_2")

    spool.push(rec1)
    spool.push(rec2)
    assert spool.count() == 2
    spool.close()

    # Reopen to test durability
    reopened = SqliteSpoolStorageAdapter(db_path=db_file)
    assert reopened.count() == 2
    assert reopened.pop().request.body == b"sqlite_1"
    assert reopened.pop().request.body == b"sqlite_2"
    assert reopened.count() == 0
    reopened.close()


def test_sqlite_spool_corrupt_detection_without_recovery(tmp_path: pytest.TempPathFactory) -> None:
    db_file = str(tmp_path / "corrupt.db")
    # Write garbage into file to corrupt SQLite header
    with open(db_file, "wb") as f:
        f.write(b"NOT A SQLITE FILE")

    with pytest.raises(SpoolStorageCorruptError):
        SqliteSpoolStorageAdapter(db_path=db_file, auto_recover_corrupt=False)


def test_sqlite_spool_corrupt_auto_recovery(tmp_path: pytest.TempPathFactory) -> None:
    db_file = str(tmp_path / "recover.db")
    with open(db_file, "wb") as f:
        f.write(b"NOT A SQLITE FILE")

    spool = SqliteSpoolStorageAdapter(db_path=db_file, auto_recover_corrupt=True)
    assert spool.count() == 0
    # Able to push cleanly after recovery
    spool.push(_make_record(1, b"recovered_payload"))
    assert spool.count() == 1
    spool.close()
