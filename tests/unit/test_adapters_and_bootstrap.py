"""Unit tests for container, bootstrap factory, rate limiters, probes, and CLI adapters."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ed_transport.adapters.driven.rate_limit.token_bucket import TokenBucketRateLimiter
from ed_transport.adapters.driven.spool.memory_spool import MemorySpoolStorageAdapter
from ed_transport.adapters.driven.spool.sqlite_spool import SqliteSpoolStorageAdapter
from ed_transport.adapters.driving.cli_health import CliHealthAdapter
from ed_transport.bootstrap.client_factory import (
    create_async_transport_client,
    create_transport_client,
)
from ed_transport.bootstrap.container import Container
from ed_transport.core.domain.health import HealthStatus, SystemHealth
from ed_transport.core.domain.models import SpoolConfig
from tests.doubles.fake_adapters import FakeSpoolStorageAdapter


class TestContainerAndBootstrap:
    """Verifies dependency injection container wiring and factory lifecycles."""

    def test_container_builds_all_adapters(self) -> None:
        container = Container(service_name="test-transport-daemon")
        probe = container.build_system_probe()
        assert probe.is_operational() is True

        metadata = probe.get_probe_metadata()
        assert "os_name" in metadata
        assert "platform" in metadata

        use_case = container.build_health_use_case()
        health = use_case.check_health()
        assert health.status == HealthStatus.HEALTHY
        assert health.service_name == "test-transport-daemon"

        cli_adapter = container.build_cli_health_adapter()
        exit_code, payload_json = cli_adapter.run()
        assert exit_code == 0
        parsed = json.loads(payload_json)
        assert parsed["status"] == "healthy"
        assert parsed["service_name"] == "test-transport-daemon"

    def test_cli_health_adapter_unhealthy_exit_code(self) -> None:
        mock_use_case = MagicMock()
        mock_use_case.check_health.return_value = SystemHealth(
            status=HealthStatus.UNHEALTHY,
            service_name="failed-daemon",
        )
        adapter = CliHealthAdapter(health_service=mock_use_case)
        exit_code, payload_json = adapter.run()
        assert exit_code == 1
        parsed = json.loads(payload_json)
        assert parsed["status"] == "unhealthy"

    def test_client_factory_injected_spool_and_sqlite_branch(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        # Explicit injected storage
        custom_storage = FakeSpoolStorageAdapter()
        client1 = create_transport_client(spool_storage=custom_storage)
        assert client1._spool_port._storage is custom_storage
        client1.close()

        # Storage via SpoolConfig storage_path
        db_path = str(tmp_path / "factory_spool.db")
        sp_cfg = SpoolConfig(storage_path=db_path, eviction_policy="RejectNewest")
        client2 = create_transport_client(spool_config=sp_cfg)
        assert isinstance(client2._spool_port._storage, SqliteSpoolStorageAdapter)
        client2._spool_port._storage.close()
        client2.close()

    @pytest.mark.asyncio
    async def test_async_client_factory_injected_spool_and_sqlite_branch(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        custom_storage = FakeSpoolStorageAdapter()
        async_client1 = create_async_transport_client(spool_storage=custom_storage)
        assert async_client1._spool_port._storage is custom_storage
        await async_client1.aclose()

        db_path = str(tmp_path / "factory_async_spool.db")
        sp_cfg = SpoolConfig(storage_path=db_path, eviction_policy="DropOldest")
        async_client2 = create_async_transport_client(spool_config=sp_cfg)
        assert isinstance(async_client2._spool_port._storage, SqliteSpoolStorageAdapter)
        async_client2._spool_port._storage.close()
        await async_client2.aclose()


class TestRateLimiterTimeouts:
    """Verifies token bucket rate limiter timeouts and replenishment."""

    def test_sync_rate_limiter_timeout(self) -> None:
        limiter = TokenBucketRateLimiter(default_rps=1.0, default_burst=1)
        # First acquire succeeds immediately
        assert limiter.acquire("destination-a") is True

        # Second acquire with short timeout expires
        assert limiter.acquire("destination-a", timeout=0.01) is False

    @pytest.mark.asyncio
    async def test_async_rate_limiter_timeout(self) -> None:
        limiter = TokenBucketRateLimiter(default_rps=1.0, default_burst=1)
        assert await limiter.acquire_async("destination-b") is True

        # Second acquire with short timeout expires
        assert await limiter.acquire_async("destination-b", timeout=0.01) is False


class TestSpoolStorageEdgeCases:
    """Verifies saturation, clear, and peek operations on SQLite and Memory spool storage."""

    def test_sqlite_spool_saturation_overflow_and_clear(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        db_file = str(tmp_path / "overflow.db")
        from ed_transport.core.domain.exceptions import SpoolCapacityExceededError
        from ed_transport.core.ports.dto.transport_dto import HttpRequestDTO, SpoolRecordDTO

        req = HttpRequestDTO(url="https://api.eddn.io", body=b"1234567890")
        record = SpoolRecordDTO(sequence_id=0, request=req, created_at=1.0)

        # Reject overflow strategy
        reject_spool = SqliteSpoolStorageAdapter(
            db_path=db_file, max_capacity_bytes=15, overflow_strategy="reject"
        )
        reject_spool.push(record)
        assert reject_spool.count() == 1

        with pytest.raises(SpoolCapacityExceededError):
            reject_spool.push(record)

        reject_spool.clear()
        assert reject_spool.count() == 0
        assert reject_spool.peek() is None
        assert reject_spool.pop() is None
        reject_spool.close()

        # Drop oldest overflow strategy
        drop_file = str(tmp_path / "drop.db")
        drop_spool = SqliteSpoolStorageAdapter(
            db_path=drop_file, max_capacity_bytes=15, overflow_strategy="drop_oldest"
        )
        req_first = HttpRequestDTO(url="https://api.eddn.io/first", body=b"1234567890")
        req_second = HttpRequestDTO(url="https://api.eddn.io/second", body=b"1234567890")

        drop_spool.push(SpoolRecordDTO(sequence_id=1, request=req_first, created_at=1.0))
        drop_spool.push(SpoolRecordDTO(sequence_id=2, request=req_second, created_at=2.0))

        assert drop_spool.count() == 1
        assert drop_spool.peek().request.url == "https://api.eddn.io/second"
        drop_spool.close()

    def test_memory_spool_peek_and_clear(self) -> None:
        from ed_transport.core.ports.dto.transport_dto import HttpRequestDTO, SpoolRecordDTO

        spool = MemorySpoolStorageAdapter(max_capacity=5)
        assert spool.peek() is None
        assert spool.pop() is None

        req = HttpRequestDTO(url="https://api.eddn.io", body=b"data")
        spool.push(SpoolRecordDTO(sequence_id=1, request=req, created_at=1.0))
        assert spool.peek() is not None
        assert spool.size_bytes() == 4

        spool.clear()
        assert spool.count() == 0
        assert spool.size_bytes() == 0
        spool.close()
