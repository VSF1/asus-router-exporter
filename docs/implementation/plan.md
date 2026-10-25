# Implementation Plan

## Index

| Phase                                | Name                     | Status      |
| ------------------------------------ | ------------------------ | ----------- |
| [001](#phase-001-initial-exporter)   | Initial Exporter         | in progress |
| [002](#phase-002-grafana-dashboard)  | Grafana Dashboard        | planned     |
| [003](#phase-003-syslog-correlation) | Syslog Correlation Notes | planned     |

---

## Phase 001: Initial Exporter

Status: in progress

### Goal

Build a working Prometheus exporter that connects to an ASUS router, collects the core metrics, and ships a multi-arch Docker image via GitHub Actions.

### Deliverables

| File                          | Purpose                                                     |
| ----------------------------- | ----------------------------------------------------------- |
| `exporter.py`                 | Main exporter — async Python using the `asusrouter` library |
| `requirements.txt`            | Pinned Python dependencies                                  |
| `Dockerfile`                  | Multi-arch image definition                                 |
| `.github/workflows/build.yml` | CI: build linux/amd64 + linux/arm64, push to GHCR           |

### Metrics

| Metric                                        | Type    | Description                                                       |
| --------------------------------------------- | ------- | ----------------------------------------------------------------- |
| `asus_router_info`                            | Info    | Model and firmware version                                        |
| `asus_scrape_success`                         | Gauge   | 1 if last scrape succeeded, 0 on failure                          |
| `asus_scrape_duration_seconds`                | Gauge   | Time taken to scrape the router                                   |
| `asus_clients_total`                          | Gauge   | Total connected clients (wired + wireless)                        |
| `asus_clients_by_band{band}`                  | Gauge   | Connected clients by WiFi band (2.4 GHz / 5 GHz / 6 GHz) or wired |
| `asus_cpu_usage_percent`                      | Gauge   | Router CPU usage percent                                          |
| `asus_cpu_core_usage_percent{core}`           | Gauge   | Router CPU usage per core                                         |
| `asus_ram_usage_percent`                      | Gauge   | Router RAM usage percent                                          |
| `asus_ram_total_bytes`                        | Gauge   | Total RAM in bytes                                                |
| `asus_ram_free_bytes`                         | Gauge   | Free RAM in bytes                                                 |
| `asus_ram_used_bytes`                         | Gauge   | Used RAM in bytes                                                 |
| `asus_system_load_average{period}`            | Gauge   | 1-, 5-, and 15-minute system load averages                        |
| `asus_temperature_celsius{sensor}`            | Gauge   | Router and radio temperatures where supported                     |
| `asus_router_uptime_seconds`                  | Gauge   | Time since the router booted                                      |
| `asus_router_boot_time_seconds`               | Gauge   | Unix timestamp of the router's last boot                          |
| `asus_connections_active`                     | Gauge   | Current active router connections                                 |
| `asus_connections_capacity`                   | Gauge   | Total router connection-table capacity                            |
| `asus_sysinfo_memory_bytes{field}`            | Gauge   | Additional system memory values, in bytes                         |
| `asus_sysinfo_swap_megabytes{slot}`           | Gauge   | Router-reported swap values by slot                               |
| `asus_wifi_clients_by_band{band,state}`       | Gauge   | WiFi clients by band and association state                        |
| `asus_wifi_radio_enabled{band}`               | Gauge   | WiFi radio enabled state by band                                  |
| `asus_wifi_channel{band}`                     | Gauge   | Configured numeric WiFi channel by band                           |
| `asus_aimesh_nodes{state}`                    | Gauge   | Aggregate online/offline AiMesh node counts                       |
| `asus_ports_total{type}`                      | Gauge   | Physical port count by type                                       |
| `asus_ports_up{type}`                         | Gauge   | Active physical links by port type                                |
| `asus_ports_link_speed_bits_per_second{type}` | Gauge   | Sum of negotiated active port speeds by type                      |
| `asus_wan_link_up{interface}`                 | Gauge   | WAN and Internet link state                                       |
| `asus_speedtest_download_bits_per_second`     | Gauge   | Latest router-reported download bandwidth                         |
| `asus_speedtest_upload_bits_per_second`       | Gauge   | Latest router-reported upload bandwidth                           |
| `asus_speedtest_latency_milliseconds`         | Gauge   | Latest router-reported speed-test latency                         |
| `asus_speedtest_jitter_milliseconds`          | Gauge   | Latest router-reported speed-test jitter                          |
| `asus_speedtest_last_run_timestamp_seconds`   | Gauge   | Timestamp of the latest router-reported speed test                |
| `asus_dsl_sync_rate{direction}`               | Gauge   | Raw DSL sync-rate value (unit not exposed by asusrouter)          |
| `asus_wan_rx_rate_bytes_per_second`           | Gauge   | WAN receive rate in bytes per second                              |
| `asus_wan_tx_rate_bytes_per_second`           | Gauge   | WAN transmit rate in bytes per second                             |
| `asus_wan_rx_bytes_total`                     | Counter | Total WAN bytes received                                          |
| `asus_wan_tx_bytes_total`                     | Counter | Total WAN bytes transmitted                                       |

### Environment Variables

| Variable          | Required | Default | Description                |
| ----------------- | -------- | ------- | -------------------------- |
| `ROUTER_HOST`     | yes      | —       | Router IP or hostname      |
| `ROUTER_USERNAME` | yes      | —       | Admin username             |
| `ROUTER_PASSWORD` | yes      | —       | Admin password             |
| `ROUTER_PORT`     | no       | `80`    | HTTP port                  |
| `ROUTER_USE_SSL`  | no       | `false` | Use HTTPS                  |
| `SCRAPE_INTERVAL` | no       | `30`    | Scrape interval in seconds |
| `PORT`            | no       | `9101`  | Metrics server port        |

### Exit Criteria

- [ ] `exporter.py` connects to a real router and exposes metrics on `/metrics`
- [ ] `asus_scrape_success` is `1` on successful scrape
- [ ] `asus_clients_by_band` shows at least one band with connected clients
- [ ] Docker image builds for both `linux/amd64` and `linux/arm64`
- [ ] GitHub Actions pushes a SHA-tagged image to GHCR on merge to main

---

## Phase 002: Grafana Dashboard

Status: planned

### Goal

Provide a reference Grafana dashboard JSON that visualises the core router metrics.
Panels should cover: client count over time per band, WAN rx/tx rates, CPU and RAM usage.

---

## Phase 003: Syslog Correlation Notes

Status: planned

### Goal

Document how to combine this exporter's time-series metrics with router syslog data (client connect/disconnect events, roaming events) for full observability.
