---
title: "Platform & Protocol Research Governance and Knowledge Base"
tags: ["architecture", "research", "governance", "index", "protocols"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Platform & Protocol Research Governance and Knowledge Base

This directory serves as the engineering ledger and single source of truth for empirical platform and network protocol research governing `ed-transport`. It captures empirical facts, wire protocol behaviors, rate-limiting quotas, connection pooling semantics, and socket mechanics verified across supported deployment environments and third-party APIs.

---

## 1. Principles & Quality Invariants

1. **Empirical Factuality:** Every research finding must be verified against actual remote endpoint behaviors (EDDN gateways, Frontier CAPI servers, Inara/EDSM endpoints, local `ed-telemetry` daemons) or verified operating system socket runtimes (native Windows, Linux, Steam Deck Proton/Wine).
2. **Immutable Traceability:** Findings document observable network behaviors, rate-limiting headers (`Retry-After`, `X-RateLimit-*`), and wire contracts at specific dates and API version baselines.
3. **Zero Repository Bloat:** Never commit large network payload dumps or packet capture `.pcap` files to this repository. Research documents must contain structured markdown, endpoint timing tables, and sanitized HTTP wire snippets.
4. **Separation from Product Logic:** Research documents record "how the external network or OS behaves", not "how `ed-transport` implements internal features". Implementation decisions belong in `architecture/adr/` or `architecture/designs/`.

---

## 2. Research Catalog

| Document | Topic | Target Endpoint / Environment | Status | Last Verified |
| :--- | :--- | :--- | :---: | :---: |
| *(Pending Research authoring)* | | | | |
