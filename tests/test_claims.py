"""Tests for Claims module."""

import logging

import pytest

from openevsehttp.exceptions import UnsupportedFeature
from tests.const import TEST_URL_CLAIMS

pytestmark = pytest.mark.asyncio


async def test_list_claims(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test list_claims function."""
    await test_charger.update()
    mock_aioclient.get(
        TEST_URL_CLAIMS,
        status=200,
        body='[{"client":65540,"priority":10,"state":"disabled","auto_release":false}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.list_claims()
    assert f"Getting claims on {TEST_URL_CLAIMS}" in caplog.text

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_v2.list_claims()
    assert "Feature not supported for older firmware." in caplog.text


async def test_release_claim(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test release_claim function."""
    await test_charger.update()
    mock_aioclient.delete(
        f"{TEST_URL_CLAIMS}/20",
        status=200,
        body='[{"msg":"done"}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.release_claim()
    assert f"Releasing claim on {TEST_URL_CLAIMS}/20" in caplog.text

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_v2.release_claim()
    assert "Feature not supported for older firmware." in caplog.text


async def test_make_claim(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test make_claim function."""
    await test_charger.update()
    mock_aioclient.post(
        f"{TEST_URL_CLAIMS}/20",
        status=200,
        body='[{"msg":"done"}]',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.make_claim(
            state="disabled", charge_current=20, max_current=20
        )
    assert (
        "Claim data: {'auto_release': True, 'state': 'disabled', 'charge_current': 20, 'max_current': 20}"
        in caplog.text
    )
    assert f"Setting up claim on {TEST_URL_CLAIMS}/20" in caplog.text

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            await test_charger.make_claim("invalid")
    assert "Invalid claim state: invalid" in caplog.text

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UnsupportedFeature):
            await test_charger_v2.make_claim()
    assert "Feature not supported for older firmware." in caplog.text
