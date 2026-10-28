#!/usr/bin/env python3
"""Operational diagnostic probe testing ed-transport against live ed-telemetry instances."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time

from ed_transport import (
    AsyncTransportClient,
    TransportClient,
    create_async_transport_client,
    create_transport_client,
)
from ed_transport.core.domain.exceptions import (
    DomainError,
    MaxRetriesExceededError,
    TransportConnectionError,
    TransportTimeoutError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_logger = logging.getLogger("probe-telemetry")


def probe_health_sync(
    client: TransportClient, base_url: str, endpoint: str, timeout: float
) -> bool:
    """Performs synchronous REST health check probe."""
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    _logger.info("Executing synchronous health probe to: %s", url)

    start_time = time.monotonic()
    try:
        response = client.get(url, timeout=timeout)
        duration_ms = (time.monotonic() - start_time) * 1000.0
        if response.is_success:
            _logger.info(
                "Health probe SUCCESS (status=%d, latency=%.1fms)",
                response.status_code,
                duration_ms,
            )
            try:
                data = json.loads(response.text)
                print("\n=== Host Health Payload ===")
                print(json.dumps(data, indent=2))
                print("===========================\n")
            except Exception:
                print(f"\nResponse Body: {response.text}\n")
            return True
        else:
            _logger.warning(
                "Health probe returned non-success (status=%d, latency=%.1fms, body=%s)",
                response.status_code,
                duration_ms,
                response.text,
            )
            return False

    except (TransportConnectionError, TransportTimeoutError, MaxRetriesExceededError) as err:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        _logger.warning(
            "Health probe FAILED: Target host unreachable after retries (latency=%.1fms): %s",
            duration_ms,
            err,
        )
        return False
    except DomainError as err:
        _logger.error("Health probe domain error: %s", err)
        return False


async def stream_telemetry_async(
    client: AsyncTransportClient,
    base_url: str,
    endpoint: str,
    topic: str | None,
    max_events: int = 0,
) -> None:
    """Streams live Server-Sent Events from ed-telemetry instance."""
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    _logger.info("Subscribing to SSE stream: %s (topic=%s)", url, topic or "ALL")
    _logger.info("Press Ctrl+C to stop streaming...")

    events_captured = 0
    start_time = time.monotonic()

    try:
        async for event in client.open_stream(endpoint=url, topic=topic):
            events_captured += 1
            elapsed = time.monotonic() - start_time

            cursor_str = f" id={event.id}" if event.id else ""
            print(
                f"\n[{elapsed:06.1f}s] Event #{events_captured}: "
                f"type='{event.event_type}'{cursor_str}"
            )
            try:
                parsed = json.loads(event.data)
                print(json.dumps(parsed, indent=2))
            except Exception:
                print(f"Data: {event.data}")

            if 0 < max_events <= events_captured:
                _logger.info("Reached maximum requested events (%d). Halting.", max_events)
                break

    except asyncio.CancelledError:
        _logger.info("Stream consumer task cancelled cleanly.")
    except Exception as err:
        _logger.error("Stream terminated with unexpected error: %s", err)
    finally:
        total_time = time.monotonic() - start_time
        print("\n=== Session Summary ===")
        print(f"Total Stream Duration: {total_time:.2f}s")
        print(f"Total Events Received: {events_captured}")
        print("=======================\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe live ed-telemetry instance using ed-transport client."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="192.168.1.214",
        help="Target host IP or hostname (default: 192.168.1.214)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Target host port (default: 8080)",
    )
    parser.add_argument(
        "--health-endpoint",
        type=str,
        default="/api/v1/health",
        help="REST health check endpoint (default: /api/v1/health)",
    )
    parser.add_argument(
        "--stream-endpoint",
        type=str,
        default="/api/v1/stream",
        help="SSE stream endpoint (default: /api/v1/stream)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Optional SSE topic filter (e.g. journal, status)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Socket timeout in seconds for synchronous probe (default: 5.0)",
    )
    parser.add_argument(
        "--mode",
        choices=["rest", "stream", "both"],
        default="both",
        help="Execution mode: rest, stream, or both (default: both)",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="Exit after N events received (default: 0 = indefinite)",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}"
    print(f"Targeting ed-telemetry at: {base_url}")

    # Mode 1: Synchronous REST probe
    if args.mode in ("rest", "both"):
        with create_transport_client() as sync_client:
            probe_health_sync(
                client=sync_client,
                base_url=base_url,
                endpoint=args.health_endpoint,
                timeout=args.timeout,
            )

    # Mode 2: Asynchronous SSE Stream
    if args.mode in ("stream", "both"):
        async with create_async_transport_client() as async_client:
            await stream_telemetry_async(
                client=async_client,
                base_url=base_url,
                endpoint=args.stream_endpoint,
                topic=args.topic,
                max_events=args.max_events,
            )

    return 0


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by operator (SIGINT). Exiting cleanly.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
