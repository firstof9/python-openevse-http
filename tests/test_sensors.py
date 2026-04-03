"""Tests for sensor data posting methods (voltage, self-production, SOC, shaper)."""

import logging

import pytest

from openevsehttp.exceptions import UnsupportedFeature

pytestmark = pytest.mark.asyncio

TEST_URL_STATUS = "http://openevse.test.tld/status"
SERVER_URL = "openevse.test.tld"


# ── self_production ──────────────────────────────────────────────────


async def test_self_production(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test self_production function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"grid_ie": 3000, "solar": 1000}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.self_production(-3000, 1000, True, 210)
        assert (
            "Posting self-production: {'grid_ie': 3000, 'voltage': 210}" in caplog.text
        )
        assert (
            "Self-production response: {'grid_ie': 3000, 'solar': 1000}" in caplog.text
        )

        await test_charger.self_production(None, 1000)
        assert "Posting self-production: {'solar': 1000}" in caplog.text

        await test_charger.self_production(None, None)
        assert "No sensor data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.self_production(-3000, 1000)
            assert "Feature not supported for older firmware." in caplog.text
        await test_charger.ws_disconnect()


# ── soc ──────────────────────────────────────────────────────────────


async def test_soc(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test soc function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"battery_level": 85, "battery_range": 230, "time_to_full_charge": 1590}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.soc(85, 230, 1590)
        assert (
            "Posting SOC data: {'battery_level': 85, 'battery_range': 230, 'time_to_full_charge': 1590}"
            in caplog.text
        )
        assert (
            "SOC response: {'battery_level': 85, 'battery_range': 230, 'time_to_full_charge': 1590}"
            in caplog.text
        )

        await test_charger.soc(voltage=220)
        assert "Posting SOC data: {'voltage': 220}" in caplog.text

        await test_charger.soc(None)
        assert "No SOC data to send to device." in caplog.text
        await test_charger.ws_disconnect()

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.soc(50, 90, 3100)
            assert "Feature not supported for older firmware." in caplog.text
        await test_charger_v2.ws_disconnect()


# ── voltage ──────────────────────────────────────────────────────────


async def test_voltage(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test voltage function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"voltage": 210}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.grid_voltage(210)
        assert "Posting voltage: {'voltage': 210}" in caplog.text
        assert "Voltage posting response: {'voltage': 210}" in caplog.text

        await test_charger.grid_voltage(None)
        assert "No sensor data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.grid_voltage(210)
            assert "Feature not supported for older firmware." in caplog.text


# ── set_shaper_live_power ────────────────────────────────────────────


async def test_set_shaper_live_power(
    test_charger, test_charger_v2, mock_aioclient, caplog
):
    """Test setting shaper live power."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"shaper_live_pwr": 210}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_shaper_live_pwr(210)
        assert "Posting shaper data: {'shaper_live_pwr': 210}" in caplog.text
        assert "Shaper response: {'shaper_live_pwr': 210}" in caplog.text

    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"shaper_live_pwr": 0}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_shaper_live_pwr(0)
        assert "Posting shaper data: {'shaper_live_pwr': 0}" in caplog.text

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.set_shaper_live_pwr(210)
    assert "Feature not supported for older firmware." in caplog.text
    await test_charger_v2.ws_disconnect()
