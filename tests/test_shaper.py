"""Tests for shaper command methods."""

import logging

import pytest

from openevsehttp.exceptions import UnknownError, UnsupportedFeature
from tests.conftest import MockClientSession

pytestmark = pytest.mark.asyncio

TEST_URL_SHAPER = "http://openevse.test.tld/shaper"


async def test_set_shaper(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test set_shaper command."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body='{"msg": "OK"}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_shaper(True)
        assert "Setting shaper to 1" in caplog.text

        await test_charger.set_shaper(False)
        assert "Setting shaper to 0" in caplog.text

    await test_charger_v2.update()
    # Force version lower than 4.0.0
    test_charger_v2._config["version"] = "3.3.1"
    with pytest.raises(UnsupportedFeature):
        await test_charger_v2.set_shaper(True)


async def test_set_shaper_fail(test_charger, mock_aioclient, caplog):
    """Test set_shaper failure."""
    await test_charger.update()
    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body='{"msg": "failure!"}',
    )
    with pytest.raises(UnknownError):
        await test_charger.set_shaper(True)


async def test_set_shaper_non_json(test_charger, mock_aioclient, caplog):
    """Test set_shaper with a non-JSON response."""
    await test_charger.update()
    test_charger._status["shaper"] = 0

    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body="Current Shaper state changed",
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_shaper(True)
        assert "Setting shaper to 1" in caplog.text
        assert test_charger.shaper_active == 1

    test_charger._status["shaper"] = 1
    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body="Current Shaper state changed",
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.set_shaper(False)
        assert "Setting shaper to 0" in caplog.text
        assert test_charger.shaper_active == 0


async def test_toggle_shaper(test_charger, mock_aioclient, caplog):
    """Test toggle_shaper command."""
    await test_charger.update()
    # Initial state from status fixture is likely True or False
    # Let's force it to 0 (off)
    test_charger._status["shaper"] = 0

    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body='{"msg": "OK"}',
    )

    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_shaper()
        assert "Setting shaper to 1" in caplog.text

    # Now it's on (1)
    test_charger._status["shaper"] = 1
    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_shaper()
        assert "Setting shaper to 0" in caplog.text


async def test_toggle_shaper_missing_state(test_charger, mock_aioclient, caplog):
    """Test toggle_shaper when state is missing."""
    # Clear status to force update()
    test_charger._status = {}

    # Mock the /status call that update() will make
    from tests.common import load_fixture

    TEST_URL_STATUS = "http://openevse.test.tld/status"
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )

    mock_aioclient.post(
        TEST_URL_SHAPER,
        status=200,
        body='{"msg": "OK"}',
    )

    with caplog.at_level(logging.DEBUG):
        await test_charger.toggle_shaper()
        # status.json has shaper: 1, so it should toggle to 0
        assert "Setting shaper to 0" in caplog.text


async def test_toggle_shaper_failed_update(mock_aioclient, caplog):
    """Test toggle_shaper when state is still missing after update()."""
    from openevsehttp import OpenEVSE

    charger = OpenEVSE("openevse.test.tld", session=MockClientSession(mock_aioclient))

    # Mock the /status call but return status without shaper
    mock_aioclient.get(
        "http://openevse.test.tld/status",
        status=200,
        body='{"mode": 1}',  # No shaper key
    )
    mock_aioclient.get(
        "http://openevse.test.tld/config",
        status=200,
        body='{"firmware": "4.1.2"}',
    )

    with pytest.raises(
        RuntimeError, match="Cannot toggle shaper: unknown shaper state."
    ):
        await charger.toggle_shaper()

    assert "Cannot toggle shaper: unknown shaper state." in caplog.text
