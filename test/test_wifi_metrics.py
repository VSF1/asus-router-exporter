"""Tests for WiFi metrics."""

import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from prometheus_client import Gauge

with patch.dict(
    os.environ,
    {
        "ROUTER_HOST": "router.example",
        "ROUTER_USERNAME": "test-user",
        "ROUTER_PASSWORD": "test-password",
    },
):
    import exporter


def _samples_by_band(metric: Gauge) -> dict[str, float]:
    return {
        sample.labels["band"]: sample.value
        for family in metric.collect()
        for sample in family.samples
    }


class TestWifiMetrics(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        exporter.wifi_radio_enabled.clear()
        exporter.wifi_channel.clear()

    async def test_scrapes_radio_state_and_numeric_channel_only(self) -> None:
        router = AsyncMock()
        router.async_get_data.return_value = {
            "2ghz": {
                "radio": True,
                "channel": "6",
                "ssid": "not-exported",
                "wpa_psk": "not-exported",
            },
            "5ghz": {
                "radio": False,
                "channel": "auto",
            },
        }

        await exporter._scrape_wifi(router)

        self.assertEqual(
            _samples_by_band(exporter.wifi_radio_enabled),
            {"2ghz": 1, "5ghz": 0},
        )
        self.assertEqual(_samples_by_band(exporter.wifi_channel), {"2ghz": 6})
        router.async_get_data.assert_awaited_once_with(exporter.AsusData.WLAN)
