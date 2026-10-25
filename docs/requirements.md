# Requirements

## Functional

- Export Prometheus metrics from ASUS routers running stock AsusWRT or Merlin firmware
- Expose connected client count broken down by WiFi band (2.4 GHz, 5 GHz, 6 GHz) or wired
- Expose total connected client count (wired + wireless)
- Expose WAN receive and transmit rates
- Expose CPU usage percent
- Expose CPU usage per core where the router provides per-core data
- Expose RAM total, free, and usage percent
- Expose used RAM in bytes
- Expose system load averages for 1, 5, and 15 minutes when supported
- Expose CPU and WiFi radio temperatures when supported
- Expose router uptime and last boot time when supported
- Expose current active connections and connection-table capacity when supported
- Expose system-information memory values (buffers, cache, JFFS, and NVRAM) when supported
- Expose router-reported swap values by slot when supported
- Expose WiFi associated, authenticated, and authorized client counts by band when supported
- Expose WiFi radio enabled state and numeric channel by band when supported
- Expose aggregate online/offline AiMesh node counts when supported
- Expose physical port totals, active-link counts, and summed negotiated speeds by port type when supported
- Expose WAN and Internet link state when supported
- Expose the latest router-reported speed-test download, upload, latency, jitter, and result timestamp when supported; do not trigger a test
- Expose raw DSL downstream and upstream sync-rate values when supported without unit conversion
- Expose cumulative WAN receive and transmit bytes and live rates when supported
- Expose router model and firmware version as an info metric
- Expose a scrape health metric (`asus_scrape_success`) so alerting can detect connectivity loss
- Support AiMesh systems — data is collected from the main router which aggregates mesh-wide client state
- Do not export per-client or per-node identifying labels, including names, MAC addresses, or IP addresses
- Do not expose SSIDs, passwords, or other sensitive wireless configuration

## Non-Functional

- All configuration via environment variables — no config files, no hard-coded values
- Credentials must never appear in logs or metric output
- Reconnect automatically if the router becomes unreachable (reboot, network blip)
- Scrape interval configurable — default 30 seconds
- Metrics port configurable — default 9101
- Multi-architecture Docker image: `linux/amd64` and `linux/arm64`
- Python 3.12+

## Constraints

- No SNMP — stock AsusWRT firmware `3.0.0.4.388+` removed the SNMP tab; supported
  traffic rates and byte totals are read from the router API
- No firmware modification — works with stock firmware as shipped
- No router-side configuration beyond enabling the admin HTTP/HTTPS interface
- Uses the `asusrouter` library for router communication — no raw HTTP session management
