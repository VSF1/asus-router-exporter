# asus-router-exporter

Prometheus exporter for ASUS routers running stock AsusWRT or Merlin firmware. Exposes
WiFi client metrics per band, WAN traffic rates and totals, CPU and memory usage,
temperatures, system load, and uptime. Supports AiMesh mesh systems. Configuration via
environment variables.

## Metrics

| Metric | Description |
|---|---|
| `asus_router_info` | Router model and firmware version (label-only) |
| `asus_scrape_success` | `1` if the last scrape succeeded, `0` on failure |
| `asus_scrape_duration_seconds` | Time spent scraping the router |
| `asus_clients_total` | Total connected clients (wired + wireless) |
| `asus_clients_by_band{band}` | Connected clients by WiFi band (`2ghz` / `5ghz` / `6ghz`) or `wired` |
| `asus_cpu_usage_percent` | CPU usage percent |
| `asus_cpu_core_usage_percent{core}` | CPU usage percent per core |
| `asus_ram_usage_percent` | RAM usage percent |
| `asus_ram_total_bytes` | Total RAM in bytes |
| `asus_ram_free_bytes` | Free RAM in bytes |
| `asus_ram_used_bytes` | Used RAM in bytes |
| `asus_system_load_average{period}` | System load averages for 1, 5, and 15 minutes |
| `asus_temperature_celsius{sensor}` | Router, CPU, and WiFi radio temperatures, when supported |
| `asus_router_uptime_seconds` | Time since the router booted |
| `asus_router_boot_time_seconds` | Unix timestamp of the router's last boot |
| `asus_connections_active` | Current active router connections |
| `asus_connections_capacity` | Total router connection-table capacity |
| `asus_sysinfo_memory_bytes{field}` | Additional system memory values (buffers, cache, JFFS, etc.) |
| `asus_sysinfo_swap_megabytes{slot}` | Router-reported swap values by slot |
| `asus_wifi_clients_by_band{band,state}` | Wireless clients by band and associated/authenticated/authorized state |
| `asus_wifi_radio_enabled{band}` | Whether each WiFi radio is enabled |
| `asus_wifi_channel{band}` | Configured numeric WiFi channel |
| `asus_aimesh_nodes{state}`                    | Aggregate online/offline AiMesh node counts |
| `asus_ports_total{type}`                      | Physical port count by port type |
| `asus_ports_up{type}`                         | Physical ports with an active link, by type |
| `asus_ports_link_speed_bits_per_second{type}` | Sum of active physical-port negotiated link speeds by type |
| `asus_wan_link_up{interface}` | WAN/Internet link state (`1` connected, `0` known disconnected) |
| `asus_speedtest_download_bits_per_second` | Most recently reported router speed-test download bandwidth |
| `asus_speedtest_upload_bits_per_second` | Most recently reported router speed-test upload bandwidth |
| `asus_speedtest_latency_milliseconds` | Most recently reported router speed-test latency |
| `asus_speedtest_jitter_milliseconds` | Most recently reported router speed-test jitter |
| `asus_speedtest_last_run_timestamp_seconds` | Unix timestamp of the most recently reported router speed test |
| `asus_dsl_sync_rate{direction}` | Router-normalized DSL downstream/upstream sync-rate value |
| `asus_wan_rx_rate_bytes_per_second` | WAN receive rate in bytes per second |
| `asus_wan_tx_rate_bytes_per_second` | WAN transmit rate in bytes per second |
| `asus_wan_rx_bytes_total` | Total WAN bytes received |
| `asus_wan_tx_bytes_total` | Total WAN bytes transmitted |

Temperature, per-core CPU, load, uptime, connection, memory, WiFi-client, and WAN network
metrics depend on firmware and router model support. AiMesh, physical-port, WAN status,
speed-test, and DSL metrics are likewise optional and appear only when the router
provides those categories. Speed-test values are the router's latest reported result;
the exporter does not trigger a speed test. The DSL sync-rate metric preserves the unit
used by the router/library because `asusrouter` does not expose a normalized unit.
WiFi radio and channel metrics use `asusrouter`'s WLAN category, but only export the
radio-enabled state and numeric channel; SSIDs, passwords, and other configuration are
not exposed. Non-numeric or automatic channel settings are omitted. Unavailable optional
measurements are omitted. System-information memory values are converted from decimal MB
to bytes; NVRAM is already reported in bytes.

The exporter reports only aggregate AiMesh and port data. It does not expose client,
node, MAC, IP, SSID, or other per-device labels. Although `asusrouter`'s WLAN response
can include credentials and other sensitive settings, only the radio-enabled state and
channel are exported.

## Quick Start

```bash
docker run -d \
  -p 9101:9101 \
  -e ROUTER_HOST=192.168.1.1 \
  -e ROUTER_USERNAME=admin \
  -e ROUTER_PASSWORD=yourpassword \
  ghcr.io/raffcorreia/asus-router-exporter:latest
```

Metrics available at `http://localhost:9101/metrics`.

## Configuration

All configuration is via environment variables.

| Variable          | Required | Default | Description                    |
| ----------------- | -------- | ------- | ------------------------------ |
| `ROUTER_HOST`     | yes      | —       | Router IP or hostname          |
| `ROUTER_USERNAME` | yes      | —       | Admin username                 |
| `ROUTER_PASSWORD` | yes      | —       | Admin password                 |
| `ROUTER_PORT`     | no       | `80`    | HTTP port (use `443` with SSL) |
| `PORT`            | no       | `9101`  | Metrics server port            |
| `ROUTER_USE_SSL`  | no       | `false` | Set `true` to use HTTPS        |
| `SCRAPE_INTERVAL` | no       | `30`    | Seconds between scrapes        |

## Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: asus_router
    static_configs:
      - targets: ["<exporter-host>:9101"]
    scrape_interval: 30s
```

## AiMesh

Point the exporter at the main router only. In an AiMesh system the main router
aggregates connected client state for all nodes, so mesh-wide client counts are
available without polling each node separately.

## Building

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t asus-router-exporter:local \
  .
```

## Documentation

- [Requirements](docs/requirements.md) — functional and non-functional requirements
- [Solution Design](docs/solution-design.md) — architecture and design decisions
- [Implementation Plan](docs/implementation/plan.md) — phased implementation roadmap

## License

MIT
