---
title: "How-To: Dispatch HTTP Requests"
tags: ["how-to", "transport-client", "http", "requests", "dispatch"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Dispatch HTTP Requests

This guide demonstrates how to dispatch synchronous and asynchronous HTTP requests using `TransportClient` and `AsyncTransportClient`.

---

## 1. Synchronous HTTP Requests (`TransportClient`)

Use `TransportClient` in synchronous scripts, worker threads, or blocking batch workloads.

### Sending GET and POST Requests

```python
import json
from ed_transport.adapters.driving import TransportClient
from ed_transport.core.domain.exceptions import TransportError

def fetch_commander_profile(client: TransportClient, commander_name: str) -> dict:
    try:
        response = client.get(
            "https://companion.orerve.net/profile",
            params={"name": commander_name},
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
        if response.is_success:
            return json.loads(response.text)
        return {"error": f"Failed with status {response.status_code}"}
    except TransportError as err:
        return {"error": f"Network error: {err}"}
```

### Context Manager Usage

Always use context manager syntax to ensure resources are cleanly released:

```python
with TransportClient(transport_port=my_port) as client:
    response = client.post(
        "https://inara.cz/inapi/v1/",
        body=json.dumps({"header": {"appName": "ed-transport"}}),
        headers={"Content-Type": "application/json"},
    )
    print(f"Status: {response.status_code}, Body: {response.text}")
```

---

## 2. Asynchronous HTTP Requests (`AsyncTransportClient`)

In reactive or `asyncio`-based environments (such as FastAPI, async workers, or GUI loops), use `AsyncTransportClient`.

### Asynchronous GET and POST

```python
import asyncio
import json
from ed_transport.adapters.driving import AsyncTransportClient
from ed_transport.core.domain.exceptions import TransportTimeoutError

async def query_system_data(async_client: AsyncTransportClient, system_name: str) -> None:
    try:
        response = await async_client.get(
            "https://www.edsm.net/api-v1/system",
            params={"systemName": system_name, "showCoordinates": "1"},
            timeout=5.0,
        )
        if response.is_success:
            print("System Coordinates:", response.text)
    except TransportTimeoutError:
        print(f"Timeout querying EDSM for {system_name}")

async def main() -> None:
    async with AsyncTransportClient(transport_port=my_async_port) as client:
        await query_system_data(client, "Sol")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Passing Query Parameters and Request Payloads

### Raw Bytes vs JSON Strings

The facade accepts payload bodies as raw `bytes` or `str`. It serializes `str` to UTF-8 encoded bytes automatically:

```python
# Passing UTF-8 string:
client.post("https://api.example.com/data", body="payload_string")

# Passing encoded raw bytes:
client.post("https://api.example.com/data", body=b"\x01\x02\x03\x04")
```

> [!IMPORTANT]
> The facade rejects Python `dict`, lists, or domain models with `InvalidPayloadTypeError`. Serialize payloads to JSON or string before passing to `post()` or `put()`.

---

## 4. Handling Transport Exceptions

Catch domain exceptions defined under `ed_transport.core.domain.exceptions`:

```python
from ed_transport.core.domain.exceptions import (
    TransportConnectionError,
    TransportTimeoutError,
    RateLimitExceededError,
    TransportError,
)

try:
    response = client.get("https://api.example.com/health")
except TransportTimeoutError:
    # Socket read or connection timeout
    logger.warning("Gateway timed out")
except TransportConnectionError:
    # DNS failure or network drop
    logger.error("Unable to reach remote host")
except RateLimitExceededError:
    # Token bucket quota exhausted
    logger.info("Throttled; backing off")
except TransportError as err:
    # Base fallback for all transport domain errors
    logger.error("Transport failed: %s", err)
```
