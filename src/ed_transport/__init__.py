"""Package root for ed-transport."""

import logging

from .adapters.driving.client import AsyncTransportClient, TransportClient
from .bootstrap.client_factory import (
    create_async_transport_client,
    create_transport_client,
)
from .core.domain.models import (
    RateLimitConfig,
    RateLimitRule,
    RetryConfig,
    SpoolConfig,
)
from .core.ports.dto.transport_dto import (
    HttpRequestDTO,
    HttpResponseDTO,
    RawStreamEventDTO,
    SpoolRecordDTO,
)

__version__ = "0.1.0"
logging.getLogger("ed_transport").addHandler(logging.NullHandler())

__all__ = (
    "AsyncTransportClient",
    "HttpRequestDTO",
    "HttpResponseDTO",
    "RateLimitConfig",
    "RateLimitRule",
    "RawStreamEventDTO",
    "RetryConfig",
    "SpoolConfig",
    "SpoolRecordDTO",
    "TransportClient",
    "__version__",
    "create_async_transport_client",
    "create_transport_client",
)
