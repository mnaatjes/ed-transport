---
title: "How-To: Configure Rate Limits"
tags: ["how-to", "ratelimit", "token-bucket", "configuration"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Configure Rate Limits

This guide explains how to set destination-specific request rates and burst capacities using `RateLimitConfig` and `TokenBucketRateLimiter`.

---

## 1. Setting Default Rate Limits

By default, clients enforce a baseline quota of 5 requests per second with a burst capacity of 10 tokens:

```python
from ed_transport import create_transport_client
from ed_transport.core.domain.models import RateLimitConfig

# Configure customized global rates
rate_cfg = RateLimitConfig(
    requests_per_second=2.0,
    burst_capacity=4,
)

with create_transport_client(rate_limit_config=rate_cfg) as client:
    resp = client.get("https://api.frontier.ed/status")
    print(resp.status_code)
```

---

## 2. Setting Destination-Specific Limits

For multi-host fleets where different endpoints have different throttling thresholds (e.g. CAPI vs EDDN), configure custom destination rules on the rate limiter adapter:

```python
from ed_transport import create_transport_client
from ed_transport.adapters.driven.rate_limit import TokenBucketRateLimiter

# Define per-destination (rps, burst) limits
custom_limiter = TokenBucketRateLimiter(
    default_rps=5.0,
    default_burst=10,
    destination_rules={
        "api.frontier.ed": (2.0, 4),
        "eddn.edcd.io": (10.0, 20),
    },
)

with create_transport_client(rate_limiter=custom_limiter) as client:
    # Requests to api.frontier.ed are throttled to 2 RPS
    client.get("https://api.frontier.ed/status")

    # Requests to eddn.edcd.io are granted up to 10 RPS
    client.get("https://eddn.edcd.io/health")
```
