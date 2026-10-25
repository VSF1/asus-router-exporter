#!/usr/bin/env python3
"""Prometheus exporter for ASUS routers via the asusrouter library."""

import asyncio
import logging
import math
import os
import time
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Info, start_http_server
from asusrouter import AsusRouter, AsusRouterError
from asusrouter.modules.connection import ConnectionState
from asusrouter.modules.data import AsusData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

ROUTER_HOST     = os.environ["ROUTER_HOST"]
ROUTER_USERNAME = os.environ["ROUTER_USERNAME"]
ROUTER_PASSWORD = os.environ["ROUTER_PASSWORD"]
ROUTER_PORT     = int(os.environ.get("ROUTER_PORT", "80"))
ROUTER_USE_SSL  = os.environ.get("ROUTER_USE_SSL", "false").lower() == "true"
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "30"))
METRICS_PORT    = int(os.environ.get("PORT", "9101"))

# ── Metrics ───────────────────────────────────────────────────────────────────

router_info       = Info("asus_router", "Router model and firmware")
scrape_success    = Gauge("asus_scrape_success", "1 if the last scrape succeeded")
scrape_duration   = Gauge("asus_scrape_duration_seconds", "Time spent scraping the router")

clients_total     = Gauge("asus_clients_total", "Total connected clients (wired + wireless)")
clients_by_band   = Gauge("asus_clients_by_band", "Connected clients by WiFi band or wired connection", ["band"])

cpu_usage         = Gauge("asus_cpu_usage_percent", "CPU usage percent")
cpu_core_usage    = Gauge("asus_cpu_core_usage_percent", "CPU usage percent by core", ["core"])

ram_usage         = Gauge("asus_ram_usage_percent", "RAM usage percent")
ram_total_bytes   = Gauge("asus_ram_total_bytes", "Total RAM in bytes")
ram_free_bytes    = Gauge("asus_ram_free_bytes", "Free RAM in bytes")
ram_used_bytes    = Gauge("asus_ram_used_bytes", "Used RAM in bytes")

wan_rx_rate_bytes = Gauge("asus_wan_rx_rate_bytes_per_second", "WAN receive rate bytes/sec")
wan_tx_rate_bytes = Gauge("asus_wan_tx_rate_bytes_per_second", "WAN transmit rate bytes/sec")
wan_rx_bytes      = Counter("asus_wan_rx_bytes", "Total WAN bytes received")
wan_tx_bytes      = Counter("asus_wan_tx_bytes", "Total WAN bytes transmitted")
load_average      = Gauge("asus_system_load_average", "System load average", ["period"])
temperature       = Gauge("asus_temperature_celsius", "Router sensor temperature in Celsius", ["sensor"])
uptime_seconds    = Gauge("asus_router_uptime_seconds", "Router uptime in seconds")
boot_time_seconds = Gauge("asus_router_boot_time_seconds", "Unix timestamp of the router's last boot")
connections_active = Gauge("asus_connections_active", "Current active router connections")
connections_capacity = Gauge("asus_connections_capacity", "Total router connection table capacity")
sysinfo_memory_bytes = Gauge(
    "asus_sysinfo_memory_bytes",
    "Router system information memory values in bytes",
    ["field"],
)
sysinfo_swap_megabytes = Gauge(
    "asus_sysinfo_swap_megabytes",
    "Router-reported swap values in megabytes",
    ["slot"],
)
wifi_clients_by_band = Gauge(
    "asus_wifi_clients_by_band",
    "Wireless clients by band and association state",
    ["band", "state"],
)
aimesh_nodes = Gauge(
    "asus_aimesh_nodes",
    "AiMesh nodes by connectivity state",
    ["state"],
)
ports_total = Gauge(
    "asus_ports_total",
    "Physical ports by type",
    ["type"],
)
ports_up = Gauge(
    "asus_ports_up",
    "Physical ports with an active link by type",
    ["type"],
)
ports_link_speed = Gauge(
    "asus_ports_link_speed_bits_per_second",
    "Sum of negotiated physical port link speeds by type",
    ["type"],
)
wan_link_up = Gauge(
    "asus_wan_link_up",
    "1 if the WAN interface is connected, 0 if a known disconnected state",
    ["interface"],
)
speedtest_download = Gauge(
    "asus_speedtest_download_bits_per_second",
    "Most recently reported router speed-test download bandwidth",
)
speedtest_upload = Gauge(
    "asus_speedtest_upload_bits_per_second",
    "Most recently reported router speed-test upload bandwidth",
)
speedtest_latency = Gauge(
    "asus_speedtest_latency_milliseconds",
    "Most recently reported router speed-test latency",
)
speedtest_jitter = Gauge(
    "asus_speedtest_jitter_milliseconds",
    "Most recently reported router speed-test jitter",
)
speedtest_timestamp_seconds = Gauge(
    "asus_speedtest_last_run_timestamp_seconds",
    "Unix timestamp of the most recently reported router speed test",
)
dsl_sync_rate = Gauge(
    "asus_dsl_sync_rate",
    "Raw DSL sync-rate value returned by asusrouter; units are not exposed",
    ["direction"],
)

_last_wan_counters: dict[str, float] = {}


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        if math.isfinite(result):
            return result
    return None


def _cpu_percent(stats: object) -> float | None:
    if not isinstance(stats, dict):
        return None
    if (usage := _number(stats.get("usage"))) is not None:
        return usage
    total = _number(stats.get("total"))
    used = _number(stats.get("used"))
    if total:
        return used / total * 100 if used is not None else None
    return None


async def _get_optional_data(router: AsusRouter, datatype: AsusData) -> object | None:
    try:
        return await router.async_get_data(datatype)
    except (AsusRouterError, IndexError, OSError, ValueError) as exc:
        log.debug("Router data %s is unavailable: %s", datatype.value, exc)
        return None

# ── Scrape helpers ────────────────────────────────────────────────────────────

async def _scrape_clients(router: AsusRouter) -> None:
    data = await router.async_get_data(AsusData.CLIENTS)
    if not isinstance(data, dict):
        return
    band_counts: dict[str, int] = {}
    total = 0
    for client in data.values():
        if getattr(client, "state", None) != ConnectionState.CONNECTED:
            continue
        conn = getattr(client, "connection", None)
        description = getattr(client, "description", None)
        if (
            conn is None
            or description is None
            or getattr(conn, "ip_address", None) is None
        ):
            continue
        total += 1
        # connection.type is a ConnectionType enum; .value is e.g. "2ghz", "5ghz", "wired"
        ctype = getattr(conn, "type", None)
        if ctype is not None:
            label = str(getattr(ctype, "value", ctype))
            band_counts[label] = band_counts.get(label, 0) + 1
    clients_total.set(total)
    clients_by_band.clear()
    for band, count in band_counts.items():
        clients_by_band.labels(band=band).set(count)


async def _scrape_cpu(router: AsusRouter) -> None:
    data = await router.async_get_data(AsusData.CPU)
    if not isinstance(data, dict):
        return
    if (total_usage := _cpu_percent(data.get("total"))) is not None:
        cpu_usage.set(total_usage)
    cpu_core_usage.clear()
    for core, stats in data.items():
        if core == "total":
            continue
        if (usage := _cpu_percent(stats)) is not None:
            cpu_core_usage.labels(core=str(core).removeprefix("cpu")).set(usage)


async def _scrape_ram(router: AsusRouter) -> None:
    # RAM values are in KB
    data = await router.async_get_data(AsusData.RAM)
    if not isinstance(data, dict):
        return
    if (usage := _number(data.get("usage"))) is not None:
        ram_usage.set(usage)
    if (total := _number(data.get("total"))) is not None:
        ram_total_bytes.set(total * 1024)
    if (free := _number(data.get("free"))) is not None:
        ram_free_bytes.set(free * 1024)
    if (used := _number(data.get("used"))) is not None:
        ram_used_bytes.set(used * 1024)


async def _scrape_wan(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.NETWORK)
    if not isinstance(data, dict):
        return
    wan = data.get("wan")
    if not isinstance(wan, dict):
        return

    for metric, key, rate_metric, rate_key in (
        (wan_rx_bytes, "rx", wan_rx_rate_bytes, "rx_speed"),
        (wan_tx_bytes, "tx", wan_tx_rate_bytes, "tx_speed"),
    ):
        if (value := _number(wan.get(key))) is not None and value >= 0:
            previous = _last_wan_counters.get(key)
            metric.inc(value if previous is None or value < previous else value - previous)
            _last_wan_counters[key] = value
        if (rate := _number(wan.get(rate_key))) is not None and rate >= 0:
            # The router reports rates in bits/s; export bytes/s.
            rate_metric.set(rate / 8)


async def _scrape_sysinfo(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.SYSINFO)
    if not isinstance(data, dict):
        return

    connections = data.get("connections")
    if isinstance(connections, dict):
        if (active := _number(connections.get("active"))) is not None:
            connections_active.set(active)
        if (capacity := _number(connections.get("total"))) is not None:
            connections_capacity.set(capacity)

    memory = data.get("memory")
    sysinfo_memory_bytes.clear()
    sysinfo_swap_megabytes.clear()
    if isinstance(memory, dict):
        for field in (
            "buffers",
            "cache",
            "free",
            "jffs_free",
            "jffs_total",
            "jffs_used",
            "total",
            "used",
        ):
            value = _number(memory.get(field))
            if value is not None:
                # The sysinfo memory fields are reported in decimal MB.
                sysinfo_memory_bytes.labels(field=field).set(value * 1_000_000)
        if (nvram := _number(memory.get("nvram"))) is not None:
            sysinfo_memory_bytes.labels(field="nvram").set(nvram)

        for slot in ("1", "2"):
            value = _number(memory.get(f"swap_{slot}"))
            if value is not None:
                sysinfo_swap_megabytes.labels(slot=slot).set(value)

    wlan = data.get("wlan")
    wifi_clients_by_band.clear()
    if isinstance(wlan, dict):
        for band, counts in wlan.items():
            if not isinstance(counts, dict):
                continue
            band_name = str(getattr(band, "value", band)).lower()
            for key, count in counts.items():
                state = str(getattr(key, "value", key)).lower()
                if state.startswith("client_"):
                    state = state.removeprefix("client_")
                value = _number(count)
                if state in {"associated", "authenticated", "authorized"} and value is not None:
                    wifi_clients_by_band.labels(
                        band=band_name,
                        state=state,
                    ).set(value)

    load_avg = data.get("load_avg")
    if not isinstance(load_avg, dict):
        load_avg = {}
    load_average.clear()
    for period in ("1", "5", "15"):
        value = _number(load_avg.get(int(period)))
        if value is None:
            value = _number(load_avg.get(period))
        if value is None:
            value = _number(data.get(f"load_avg_{period}"))
        if value is None:
            value = _number(data.get(f"load_avg{period}"))
        if value is not None:
            load_average.labels(period=f"{period}m").set(value)


async def _scrape_temperatures(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.TEMPERATURE)
    if not isinstance(data, dict):
        return
    sensor_names = {
        "2ghz": "2ghz",
        "5ghz": "5ghz",
        "5ghz2": "5ghz2",
        "5ghz_2": "5ghz2",
        "6ghz": "6ghz",
        "cpu": "cpu",
    }
    temperature.clear()
    for name, value in data.items():
        sensor_key = str(getattr(name, "value", name)).lower()
        sensor_name = sensor_names.get(sensor_key)
        temp = _number(value)
        if sensor_name is not None and temp is not None:
            temperature.labels(sensor=sensor_name).set(temp)


def _as_timestamp(value: object) -> float | None:
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return _number(value)


async def _scrape_uptime(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.BOOTTIME)
    if not isinstance(data, dict):
        return
    if (uptime := _number(data.get("uptime"))) is not None and uptime >= 0:
        uptime_seconds.set(uptime)
    if (boot_time := _as_timestamp(data.get("datetime"))) is not None:
        boot_time_seconds.set(boot_time)


async def _scrape_aimesh(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.AIMESH)
    if not isinstance(data, dict):
        return

    counts = {"online": 0, "offline": 0}
    for node in data.values():
        state = getattr(node, "status", None)
        if isinstance(state, bool):
            counts["online" if state else "offline"] += 1

    aimesh_nodes.clear()
    for state, count in counts.items():
        aimesh_nodes.labels(state=state).set(count)


def _port_groups(
    data: dict[object, object],
) -> dict[str, list[dict[object, object]]]:
    groups: dict[str, list[dict[object, object]]] = {}
    known_types = {
        "ethernet",
        "lan",
        "moca",
        "powerline",
        "sfpp",
        "unknown",
        "usb",
        "wan",
    }
    for key, value in data.items():
        port_type = str(getattr(key, "value", key)).lower()
        if port_type in known_types and isinstance(value, dict):
            groups.setdefault(port_type, []).append(value)
            continue

        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                nested_type = str(
                    getattr(nested_key, "value", nested_key)
                ).lower()
                if nested_type in known_types and isinstance(nested_value, dict):
                    groups.setdefault(nested_type, []).append(nested_value)
    return groups


async def _scrape_ports(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.PORTS)
    if not isinstance(data, dict):
        return

    totals: dict[str, int] = {}
    active: dict[str, int] = {}
    speeds: dict[str, float] = {}
    for port_type, port_maps in _port_groups(data).items():
        for port_map in port_maps:
            for details in port_map.values():
                if not isinstance(details, dict):
                    continue
                totals[port_type] = totals.get(port_type, 0) + 1
                state = details.get("state")
                if state is True:
                    active[port_type] = active.get(port_type, 0) + 1
                rate = _number(details.get("link_rate"))
                if state is True and rate is not None and rate > 0:
                    # asusrouter represents Ethernet link rates in megabits/s.
                    speeds[port_type] = speeds.get(port_type, 0.0) + rate * 1_000_000

    ports_total.clear()
    ports_up.clear()
    ports_link_speed.clear()
    for port_type, count in totals.items():
        ports_total.labels(type=port_type).set(count)
        ports_up.labels(type=port_type).set(active.get(port_type, 0))
    for port_type, speed in speeds.items():
        ports_link_speed.labels(type=port_type).set(speed)


def _known_wan_state(value: object, *, status_enum: bool) -> float | None:
    state_name = getattr(value, "name", None)
    if state_name == "CONNECTED":
        return 1
    if state_name in {"DISCONNECTED", "CONNECTING", "ERROR"}:
        return 0

    # The library uses ConnectionStatus.CONNECTED=2 for Internet status and
    # ConnectionState.CONNECTED=1 for physical WAN links.
    number = _number(getattr(value, "value", value))
    if number is None:
        return None
    if status_enum:
        if number == 2:
            return 1
        return 0 if number in {-1, 0, 1} else None
    if number == 1:
        return 1
    return 0 if number == 0 else None


async def _scrape_wan_status(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.WAN)
    if not isinstance(data, dict):
        return

    wan_link_up.clear()
    internet = data.get("internet")
    if isinstance(internet, dict):
        state = _known_wan_state(internet.get("link"), status_enum=True)
        if state is not None:
            wan_link_up.labels(interface="internet").set(state)

    for unit in (0, 1):
        interface = data.get(unit)
        if not isinstance(interface, dict):
            continue
        state = interface.get("state")
        if state is not None:
            is_up = _known_wan_state(state, status_enum=True)
        else:
            is_up = _known_wan_state(interface.get("link"), status_enum=False)
        if is_up is not None:
            wan_link_up.labels(interface=f"wan{unit}").set(is_up)


async def _scrape_speedtest(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.SPEEDTEST)
    if not isinstance(data, dict):
        return

    if (timestamp := _as_timestamp(data.get("timestamp"))) is not None:
        speedtest_timestamp_seconds.set(timestamp)

    for direction, metric in (
        ("download", speedtest_download),
        ("upload", speedtest_upload),
    ):
        result = data.get(direction)
        bandwidth = (
            _number(result.get("bandwidth"))
            if isinstance(result, dict)
            else None
        )
        if bandwidth is not None and bandwidth >= 0:
            # asusrouter normalizes Ookla bandwidth to bits/s.
            metric.set(bandwidth)

    ping = data.get("ping")
    if isinstance(ping, dict):
        for field, metric in (
            ("latency", speedtest_latency),
            ("jitter", speedtest_jitter),
        ):
            value = _number(ping.get(field))
            if value is not None and value >= 0:
                metric.set(value)


async def _scrape_dsl(router: AsusRouter) -> None:
    data = await _get_optional_data(router, AsusData.DSL)
    if not isinstance(data, dict):
        return

    dsl_sync_rate.clear()
    datarate = data.get("datarate")
    if not isinstance(datarate, dict):
        return

    for direction in ("down", "up"):
        value = _number(datarate.get(direction))
        if value is not None and value >= 0:
            dsl_sync_rate.labels(direction=direction).set(value)


async def scrape(router: AsusRouter) -> None:
    start = time.monotonic()
    try:
        await asyncio.gather(
            _scrape_clients(router),
            _scrape_cpu(router),
            _scrape_ram(router),
            _scrape_wan(router),
            _scrape_sysinfo(router),
            _scrape_temperatures(router),
            _scrape_uptime(router),
            _scrape_aimesh(router),
            _scrape_ports(router),
            _scrape_wan_status(router),
            _scrape_speedtest(router),
            _scrape_dsl(router),
        )
        scrape_success.set(1)
    except Exception as exc:
        log.warning("Scrape error: %s", exc)
        scrape_success.set(0)
    finally:
        scrape_duration.set(time.monotonic() - start)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    log.info(
        "asus-router-exporter starting — target=%s port=%d interval=%ds",
        ROUTER_HOST, METRICS_PORT, SCRAPE_INTERVAL,
    )
    start_http_server(METRICS_PORT)

    while True:
        router = AsusRouter(
            hostname=ROUTER_HOST,
            username=ROUTER_USERNAME,
            password=ROUTER_PASSWORD,
            port=ROUTER_PORT,
            use_ssl=ROUTER_USE_SSL,
        )
        try:
            await router.async_connect()
            info_labels: dict[str, str] = {}
            try:
                fw = await router.async_get_data(AsusData.FIRMWARE)
                if fw and isinstance(fw, dict):
                    info_labels["firmware"] = str(fw.get("current", "unknown"))
            except (AsusRouterError, OSError, ValueError) as exc:
                log.warning("Unable to read router firmware: %s", exc)
            try:
                identity = await router.async_get_identity()
                if model := getattr(identity, "model", None):
                    info_labels["model"] = str(model)
                if firmware := getattr(identity, "firmware", None):
                    info_labels["firmware"] = str(firmware)
            except (AsusRouterError, OSError, ValueError) as exc:
                log.warning("Unable to read router identity: %s", exc)
            if info_labels:
                router_info.info(info_labels)

            log.info("Connected to router at %s", ROUTER_HOST)
            while True:
                await scrape(router)
                await asyncio.sleep(SCRAPE_INTERVAL)

        except Exception as exc:
            log.error("Connection failed: %s — retrying in 60s", exc)
            scrape_success.set(0)
        finally:
            try:
                await router.async_disconnect()
            except Exception:
                pass
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
