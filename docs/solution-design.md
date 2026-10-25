# Solution Design

## Overview

The exporter is a single Python process that polls an ASUS router's local HTTP API on a
configurable interval and exposes the results as Prometheus metrics on `/metrics`.
It follows the sensor surface of the [Home Assistant ASUSWRT integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/asuswrt),
using the same `asusrouter` data categories for CPU, network, RAM, system information,
temperatures, and boot time. Optional sensor families are omitted when the router does
not support them.

## Design Decisions

### Library: asusrouter (Vaskivskyi)

The `asusrouter` library ([PyPI](https://pypi.org/project/asusrouter/)) is used for all
router communication. It handles HTTP authentication, session management, and response
parsing for a wide range of ASUS firmware versions.

Alternatives considered:

| Option | Reason rejected |
|---|---|
| Raw HTTP (reverse-engineered endpoints) | Fragile — firmware updates change endpoints |
| CipherDoc34/asus-prometheus-exporter (Go) | No WiFi client data; no published Docker image |
| Fork of RafaelMoreira1180778/asus-router-monitoring | docker-compose stack, not a standalone exporter; still uses asusrouter internally |
| SNMP | Removed from stock firmware `3.0.0.4.388+` |

### Single target per instance

Each exporter instance monitors one router. For AiMesh systems, the main router aggregates
client state for all nodes — polling only the main router is sufficient to get mesh-wide
client counts. Individual node metrics (per-node CPU, RAM) are not available through the
main router API and are not in scope.

### Metrics and units

Network counters and rates are read from `AsusData.NETWORK`. The router reports rates in
bits per second, which the exporter converts to bytes per second to match the exported
metric names. Cumulative WAN counters are exposed as Prometheus counters and adjusted
for router-side counter resets. RAM values are reported in KiB by the router and
converted to bytes. CPU per-core values, load averages, temperatures, uptime, and boot
time are exposed when present. The system-information response also provides connection
activity/capacity, WiFi client counts by band and association state, and memory details.
Memory fields reported in decimal MB are converted to bytes; NVRAM is already in bytes.
Swap values are exported by their router-provided slot without assigning used/total
semantics that the response does not define.

Additional optional collectors use the `AIMESH`, `PORTS`, `WAN`, `SPEEDTEST`, and `DSL`
categories. AiMesh nodes and ports are aggregated without node, MAC, or IP labels.
Port link speeds are summed by port type and converted from the library's Mbit/s values
to bits/s. WAN metrics expose only recognized connection state. Speed-test metrics use
the latest result already held by the router; the exporter does not initiate tests.
The result timestamp is exported so consumers can distinguish a fresh result from an
older one.
DSL sync rates retain the raw numeric values from `asusrouter` because the library
discards the original unit strings. The exporter deliberately does not scrape WLAN or
guest-WLAN configuration or raw ping diagnostics: their responses may include sensitive
settings or lack a stable normalized metric schema.

### Async-native

`asusrouter` is an async library. The exporter uses `asyncio` throughout and fetches all
metric categories concurrently within each scrape using `asyncio.gather`. Errors from
optional categories are logged at debug level without marking the entire scrape failed;
failures in the existing client, CPU, or RAM collection still mark the scrape failed.

### Connection lifecycle

The router is connected once and polled across scrape intervals, then disconnected when
the loop exits or a connection failure occurs. If the connection drops (router reboot,
network blip), the outer `while True` loop catches the exception, sets
`asus_scrape_success=0`, disconnects, and retries after 60 seconds.

### Defensive attribute access

Router firmware versions differ in which fields are populated. All attribute reads use
`getattr(obj, "attr", None)` and skip metric updates when data is absent. This ensures
the exporter works across firmware versions without crashing on missing fields.

### Image tagging

Images are tagged with the git SHA (`ghcr.io/<repo>:<sha>`) for reproducibility. The
`latest` tag is also pushed for convenience but deployments should always pin to the SHA.

### GitHub-hosted runner

The CI pipeline runs on `ubuntu-latest` (GitHub-hosted). The build step — `docker build`
+ `docker push to GHCR` + `git commit to infra repo` — requires no cluster access.
Using a GitHub-hosted runner avoids the risk of arbitrary PR code executing on private
self-hosted infrastructure.

### Security

- Credentials are injected at runtime via environment variables only
- Credentials never appear in logs — the exporter logs the target hostname only
- The Docker image runs as `nobody` (non-root)
- The router HTTP password is stored in a secrets manager in the deployment environment;
  it is never committed to any repository
