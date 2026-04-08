"""Tests for manager methods (override, limits, claims CRUD)."""

import json
import logging

import pytest

from openevsehttp.exceptions import (
    InvalidType,
    UnsupportedFeature,
)

pytestmark = pytest.mark.asyncio

TEST_URL_OVERRIDE = "http://openevse.test.tld/override"
TEST_URL_LIMIT = "http://openevse.test.tld/limit"
TEST_URL_CLAIMS = "http://openevse.test.tld/claims"
SERVER_URL = "openevse.test.tld"


# ── set_override ────────────────────────────────────────────────────


async def test_set_override(
    test_charger, test_charger_v2, test_charger_unknown_semver, mock_aioclient, caplog
):
    """Test set override function."""
    await test_charger.update()
    value = {
        "state": "active",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.set_override("active")
        assert status == {"msg": "OK"}
        assert (
            "Override data: {'state': 'active', 'charge_current': 0, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )

        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override(charge_current=30)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 0, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 0, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32, 2000)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 0, 'auto_release': True}"
            in caplog.text
        )
        mock_aioclient.post(
            TEST_URL_OVERRIDE,
            status=200,
            body='{"msg": "OK"}',
        )
        status = await test_charger.set_override("active", 30, 32, 2000, 5000)
        assert (
            "Override data: {'state': 'active', 'charge_current': 30, 'max_current': 32, 'energy_limit': 2000, 'time_limit': 5000, 'auto_release': True}"
            in caplog.text
        )

    with pytest.raises(ValueError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.set_override("invalid")
    assert "Invalid override state: invalid" in caplog.text

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            status = await test_charger_v2.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text
    caplog.clear()

    await test_charger_unknown_semver.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            status = await test_charger_unknown_semver.set_override("active")
    assert "Feature not supported for older firmware." in caplog.text


# ── clear_override ──────────────────────────────────────────────────


async def test_clear_override(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test clear override function."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "OK"}',
    )
    with caplog.at_level(logging.DEBUG):
        await test_charger.clear_override()
        assert "Clear override response: OK" in caplog.text

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.clear_override()
    assert "Feature not supported for older firmware." in caplog.text


async def test_clear_override_fail(test_charger, mock_aioclient, caplog):
    """Test clear_override HTTP failure."""
    await test_charger.update()
    mock_aioclient.delete(
        TEST_URL_OVERRIDE,
        status=200,
        body='{"msg": "failure!"}',
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Failed to clear override:"):
            await test_charger.clear_override()
    assert "Problem clearing override: {'msg': 'failure!'}" in caplog.text


# ── get_override ────────────────────────────────────────────────────


async def test_get_override(test_charger, test_charger_v2, mock_aioclient, caplog):
    """Test get override function."""
    await test_charger.update()
    value = {
        "state": "active",
        "charge_current": 0,
        "max_current": 0,
        "energy_limit": 0,
        "time_limit": 0,
        "auto_release": True,
    }
    mock_aioclient.get(
        TEST_URL_OVERRIDE,
        status=200,
        body=json.dumps(value),
    )
    with caplog.at_level(logging.DEBUG):
        status = await test_charger.get_override()
        assert status == value

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.get_override()
    assert "Feature not supported for older firmware." in caplog.text


# ── set_limit / get_limit / clear_limit ──────────────────────────────


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

    await test_charger.update()
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

    await test_charger.update()
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

    await test_charger.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger.clear_limit()
    assert "Feature not supported for older firmware." in caplog.text


# ── list_claims / release_claim / make_claim ─────────────────────────


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

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
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

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
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

    with pytest.raises(ValueError):
        with caplog.at_level(logging.DEBUG):
            await test_charger.make_claim("invalid")
    assert "Invalid claim state: invalid" in caplog.text

    await test_charger_v2.update()
    with pytest.raises(UnsupportedFeature):
        with caplog.at_level(logging.DEBUG):
            await test_charger_v2.make_claim()
    assert "Feature not supported for older firmware." in caplog.text
