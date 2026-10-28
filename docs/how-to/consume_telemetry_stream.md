---
title: "How-To: Consume Telemetry Stream"
tags: ["how-to", "transport-client", "telemetry", "streaming", "sse", "events"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Consume Telemetry Stream

This guide demonstrates how to consume real-time telemetry streams from local daemons (e.g. Server-Sent Events over HTTP) using `AsyncTransportClient.open_stream()`.

---

## 1. Opening an SSE Telemetry Stream

To subscribe to telemetry events from a local background daemon or service, invoke `open_stream()` on `AsyncTransportClient`:

```python
import asyncio
from ed_transport.adapters.driving import AsyncTransportClient
from ed_transport.core.ports.dto import RawStreamEventDTO

async def handle_telemetry() -> None:
    async with AsyncTransportClient(stream_port=stream_adapter) as client:
        # Subscribe to the 'journal' topic on local daemon SSE endpoint
        async for event in client.open_stream(
            endpoint="http://127.0.0.1:8080/events",
            topic="journal"
        ):
            print(f"Event: {event.event_type}, ID: {event.id}")
            print(f"Payload: {event.data}")

if __name__ == "__main__":
    asyncio.run(handle_telemetry())
```

---

## 2. Parsing Stream Event Data

The stream yields immutable `RawStreamEventDTO` instances containing:
* `event.event_type`: Event category or SSE event name (defaults to `"message"`).
* `event.data`: Event payload decoded as a UTF-8 string.
* `event.id`: Optional monotonic event identifier (used for reconnection cursors via `Last-Event-ID`).
* `event.retry`: Optional reconnection delay directive in milliseconds.

### Example: Decoding JSON Events

```python
import json

async def process_stream(client: AsyncTransportClient) -> None:
    async for event in client.open_stream("http://127.0.0.1:8080/events", "status"):
        if event.data:
            payload = json.loads(event.data)
            print(f"Received status update for Commander {payload.get('Commander')}")
```

> [!TIP]
> The underlying stream port adapter automatically handles reconnects and SSE backpressure. If no stream port is wired to `AsyncTransportClient`, `open_stream()` yields nothing.
