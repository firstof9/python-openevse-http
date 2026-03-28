"""Tests for Limit module."""

import logging

import pytest

from openevsehttp.exceptions import InvalidType, UnsupportedFeature
from tests.const import TEST_URL_LIMIT

pytestmark = pytest.mark.asyncio


async def test_set_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test set limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=200,
        body='{"type": "energy", "value": 10}',
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_LIMIT,
        status=200,
        body='{"msg": "OK"}',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger_modified_ver.set_limit("energy", 15, True)
        assert (
            "Limit data: {'type': 'energy', 'value': 15, 'release': True}"
            in caplog.text
        )
        assert "Setting limit config on http://openevse.test.tld/limit" in caplog.text

    with pytest.raises(InvalidType):
        await test_charger_modified_ver.set_limit("invalid", 15)

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_limit("energy", 15)
            assert "Feature not supported for older firmware." in caplog.text


async def test_get_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test get limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=200,
        body='{"type": "energy", "value": 10}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.get_limit()
        assert response == {"type": "energy", "value": 10}
        assert "Getting limit config on http://openevse.test.tld/limit" in caplog.text

    mock_aioclient.get(
        TEST_URL_LIMIT,
        status=404,
        body='{"msg": "No limit"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.get_limit()
        assert response == {"msg": "No limit"}

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.get_limit()
            assert "Feature not supported for older firmware." in caplog.text


async def test_clear_limit(
    test_charger_modified_ver, test_charger, mock_aioclient, caplog
):
    """Test clear limit."""
    await test_charger_modified_ver.update()
    mock_aioclient.delete(
        TEST_URL_LIMIT,
        status=200,
        body='{"msg": "Deleted"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.clear_limit()
        assert response == {"msg": "Deleted"}
        assert "Clearing limit config on http://openevse.test.tld/limit" in caplog.text

    mock_aioclient.delete(
        TEST_URL_LIMIT,
        status=404,
        body='{"msg": "No limit to clear"}',
    )
    with caplog.at_level(logging.DEBUG):
        response = await test_charger_modified_ver.clear_limit()
        assert response == {"msg": "No limit to clear"}

    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.clear_limit()
            assert "Feature not supported for older firmware." in caplog.text
