"""Boundary Data Transfer Objects (DTOs) for driving and driven ports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...domain.exceptions import DomainValidationError
from ..base import DataTransferObject


@dataclass(frozen=True)
class HttpRequestDTO(DataTransferObject):
    """Immutable data transfer object representing an outbound HTTP request."""

    url: str
    method: str = "GET"
    headers: Mapping[str, str] = frozenset()  # type: ignore[assignment]
    body: bytes = b""
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """Validates request invariants."""
        if not self.url or not (self.url.startswith("http://") or self.url.startswith("https://")):
            raise DomainValidationError(f"Invalid request URL scheme: '{self.url}'")
        if self.method not in {"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"}:
            raise DomainValidationError(f"Invalid or unsupported HTTP method: '{self.method}'")
        if self.timeout <= 0.0:
            raise DomainValidationError(f"Request timeout must be positive, got {self.timeout}")


@dataclass(frozen=True)
class HttpResponseDTO(DataTransferObject):
    """Immutable data transfer object representing a received HTTP response."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def __post_init__(self) -> None:
        """Validates response invariants."""
        if not (100 <= self.status_code <= 599):
            raise DomainValidationError(f"Invalid HTTP status code: {self.status_code}")

    @property
    def is_success(self) -> bool:
        """Returns True if status code is in 2xx range."""
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        """Decodes body bytes as UTF-8 string."""
        return self.body.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RawStreamEventDTO(DataTransferObject):
    """Immutable representation of an unparsed Server-Sent Event frame."""

    event_type: str
    data: str
    id: str | None = None
    retry: int | None = None
