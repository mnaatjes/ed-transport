"""Factory functions for creating production-ready synchronous and asynchronous TransportClients."""

from __future__ import annotations

import httpx

from ..adapters.driven.engine.httpx_engine import (
    HttpxAsyncEngineAdapter,
    HttpxSyncEngineAdapter,
)
from ..adapters.driven.rate_limit.token_bucket import TokenBucketRateLimiter
from ..adapters.driven.spool.memory_spool import MemorySpoolStorageAdapter
from ..adapters.driven.spool.sqlite_spool import SqliteSpoolStorageAdapter
from ..adapters.driven.stream.sse_stream import SseStreamEngineAdapter
from ..adapters.driving.client import AsyncTransportClient, TransportClient
from ..core.domain.models import RateLimitConfig, RetryConfig, SpoolConfig
from ..core.ports.driven.engine_port import (
    AsyncTransportEnginePort,
    TransportEnginePort,
)
from ..core.ports.driven.rate_limiter_port import RateLimiterPort
from ..core.ports.driven.spool_storage_port import SpoolStoragePort
from ..core.ports.driven.stream_engine_port import StreamEnginePort
from ..core.use_cases.consume_stream import ConsumeTelemetryStreamUseCase
from ..core.use_cases.drain_spool import DrainSpoolBufferUseCase
from ..core.use_cases.execute_request import ExecuteHttpRequestUseCase
from ..core.use_cases.execute_request_async import AsyncExecuteHttpRequestUseCase


def create_transport_client(
    rate_limit_config: RateLimitConfig | None = None,
    retry_config: RetryConfig | None = None,
    spool_config: SpoolConfig | None = None,
    default_timeout: float = 30.0,
    *,
    engine: TransportEnginePort | None = None,
    rate_limiter: RateLimiterPort | None = None,
    spool_storage: SpoolStoragePort | None = None,
    httpx_client: httpx.Client | None = None,
) -> TransportClient:
    """Instantiates a fully wired, production-ready synchronous TransportClient.

    If spool_config.storage_path is not specified, defaults to MemorySpoolStorageAdapter
    strictly adhering to library invariants (no unprompted filesystem creation).
    """
    rl_cfg = rate_limit_config or RateLimitConfig()
    rt_cfg = retry_config or RetryConfig()
    sp_cfg = spool_config or SpoolConfig()

    eng = engine or HttpxSyncEngineAdapter(client=httpx_client)
    rl = rate_limiter or TokenBucketRateLimiter(
        default_rps=rl_cfg.requests_per_second,
        default_burst=rl_cfg.burst_capacity,
    )

    if spool_storage is not None:
        storage = spool_storage
    elif sp_cfg.storage_path:
        storage = SqliteSpoolStorageAdapter(
            db_path=sp_cfg.storage_path,
            max_capacity_bytes=sp_cfg.memory_limit_bytes,
            overflow_strategy="drop_oldest" if sp_cfg.eviction_policy == "DropOldest" else "reject",
            auto_recover_corrupt=sp_cfg.auto_recover_corrupt,
        )
    else:
        storage = MemorySpoolStorageAdapter(
            max_capacity=sp_cfg.max_capacity,
            memory_limit_bytes=sp_cfg.memory_limit_bytes,
            eviction_policy=sp_cfg.eviction_policy,
        )

    transport_use_case = ExecuteHttpRequestUseCase(
        engine=eng,
        rate_limiter=rl,
        retry_config=rt_cfg,
        rate_limit_config=rl_cfg,
    )
    spool_use_case = DrainSpoolBufferUseCase(
        storage=storage,
        transport=transport_use_case,
    )

    return TransportClient(
        transport_port=transport_use_case,
        spool_port=spool_use_case,
        rate_limit_config=rl_cfg,
        retry_config=rt_cfg,
        spool_config=sp_cfg,
        default_timeout=default_timeout,
    )


def create_async_transport_client(
    rate_limit_config: RateLimitConfig | None = None,
    retry_config: RetryConfig | None = None,
    spool_config: SpoolConfig | None = None,
    default_timeout: float = 30.0,
    *,
    engine: AsyncTransportEnginePort | None = None,
    rate_limiter: RateLimiterPort | None = None,
    spool_storage: SpoolStoragePort | None = None,
    stream_engine: StreamEnginePort | None = None,
    httpx_client: httpx.AsyncClient | None = None,
) -> AsyncTransportClient:
    """Instantiates a fully wired, production-ready asynchronous AsyncTransportClient."""
    rl_cfg = rate_limit_config or RateLimitConfig()
    rt_cfg = retry_config or RetryConfig()
    sp_cfg = spool_config or SpoolConfig()

    eng = engine or HttpxAsyncEngineAdapter(client=httpx_client)
    rl = rate_limiter or TokenBucketRateLimiter(
        default_rps=rl_cfg.requests_per_second,
        default_burst=rl_cfg.burst_capacity,
    )

    if spool_storage is not None:
        storage = spool_storage
    elif sp_cfg.storage_path:
        storage = SqliteSpoolStorageAdapter(
            db_path=sp_cfg.storage_path,
            max_capacity_bytes=sp_cfg.memory_limit_bytes,
            overflow_strategy="drop_oldest" if sp_cfg.eviction_policy == "DropOldest" else "reject",
            auto_recover_corrupt=sp_cfg.auto_recover_corrupt,
        )
    else:
        storage = MemorySpoolStorageAdapter(
            max_capacity=sp_cfg.max_capacity,
            memory_limit_bytes=sp_cfg.memory_limit_bytes,
            eviction_policy=sp_cfg.eviction_policy,
        )

    transport_use_case = AsyncExecuteHttpRequestUseCase(
        engine=eng,
        rate_limiter=rl,
        retry_config=rt_cfg,
        rate_limit_config=rl_cfg,
    )
    from ..core.use_cases.drain_spool import AsyncDrainSpoolBufferUseCase

    spool_use_case = AsyncDrainSpoolBufferUseCase(
        storage=storage,
        transport=transport_use_case,
    )
    s_engine = stream_engine or SseStreamEngineAdapter(client=httpx_client)
    stream_use_case = ConsumeTelemetryStreamUseCase(stream_engine=s_engine)

    return AsyncTransportClient(
        transport_port=transport_use_case,
        spool_port=spool_use_case,  # type: ignore[arg-type]
        stream_port=stream_use_case,
        rate_limit_config=rl_cfg,
        retry_config=rt_cfg,
        spool_config=sp_cfg,
        default_timeout=default_timeout,
    )
