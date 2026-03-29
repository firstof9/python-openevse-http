"""Tests for Sensors module."""

import logging

import pytest

from openevsehttp.exceptions import UnsupportedFeature
from tests.const import TEST_URL_STATUS

pytestmark = pytest.mark.asyncio


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


async def test_self_production(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test self_production function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"grid_ie": 210}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.self_production(210)
        assert "Posting self-production: {'grid_ie': -210}" in caplog.text
        assert "Self-production response: {'grid_ie': 210}" in caplog.text

        # Test solar and voltage
        await test_charger.self_production(solar=500, voltage=230)
        assert "Posting self-production: {'solar': 500, 'voltage': 230}" in caplog.text

        await test_charger.self_production(None)
        assert "No sensor data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.self_production(210)
            assert "Feature not supported for older firmware." in caplog.text


async def test_soc(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test soc function."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_STATUS,
        status=200,
        body='{"vehicle_soc": 210}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.soc(210)
        assert "Posting SOC data: {'battery_level': 210}" in caplog.text
        assert "SOC response: {'vehicle_soc': 210}" in caplog.text

        # Test battery_range and time_to_full and voltage
        await test_charger.soc(battery_range=100, time_to_full=60, voltage=230)
        assert "Posting SOC data: {'battery_range': 100, 'time_to_full_charge': 60, 'voltage': 230}" in caplog.text

        await test_charger.soc(None)
        assert "No SOC data to send to device." in caplog.text

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.soc(210)
            assert "Feature not supported for older firmware." in caplog.text


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
