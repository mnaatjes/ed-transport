"""Unit tests for client factory bootstrap functions."""

from __future__ import annotations

from ed_transport import create_async_transport_client, create_transport_client
from ed_transport.adapters.driving.client import AsyncTransportClient, TransportClient
from tests.doubles.fake_adapters import FakeTransportEngineAdapter


def test_create_transport_client_defaults_to_in_memory() -> None:
    client = create_transport_client(engine=FakeTransportEngineAdapter())
    assert isinstance(client, TransportClient)
    assert client.spool_depth == 0


def test_create_async_transport_client_defaults() -> None:
    client = create_async_transport_client()
    assert isinstance(client, AsyncTransportClient)
    assert client.spool_depth == 0
