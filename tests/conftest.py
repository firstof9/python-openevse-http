"""Provide common pytest fixtures."""

import json

import pytest
from aioresponses import aioresponses

import openevsehttp.__main__ as main
from tests.common import load_fixture

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_WS = "ws://openevse.test.tld/ws"
TEST_TLD = "openevse.test.tld"


@pytest.fixture(name="test_charger_auth")
def test_charger_auth(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("v4_json/status.json"),
        repeat=True,
    )
    return main.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


@pytest.fixture(name="test_charger_auth_err")
def test_charger_auth_err(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=401,
    )
    return main.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


@pytest.fixture(name="test_charger")
def test_charger(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config.json"),
    )
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("v4_json/status.json"),
        repeat=True,
    )
    return main.OpenEVSE(TEST_TLD)

@pytest.fixture(name="test_charger_timeout")
def test_charger_timeout(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        exception=TimeoutError,
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_dev")
def test_charger_dev(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-dev.json"),
    )
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("v4_json/status.json"),
        repeat=True,
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_new")
def test_charger_new(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status-new.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-new.json"),
    )
    mock_aioclient.get(
        TEST_URL_WS,
        status=200,
        body=load_fixture("v4_json/status-new.json"),
        repeat=True,
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_broken")
def test_charger_broken(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status-broken.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-broken.json"),
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_broken_semver")
def test_charger_broken_semver(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-broken-semver.json"),
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_unknown_semver")
def test_charger_unknown_semver(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-unknown-semver.json"),
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_modified_ver")
def test_charger_modified_ver(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v4_json/config-extra-version.json"),
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_v2")
def test_charger_v2(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v2_json/status.json"),
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=load_fixture("v2_json/config.json"),
    )
    return main.OpenEVSE(TEST_TLD)


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with aioresponses() as mock_aiohttp:
        mock_headers = {"content-type": "application/json"}
        mock_aiohttp.get(
            "ws://openevse.test.tld/ws",
            status=200,
            headers=mock_headers,
            body={},
        )

        yield mock_aiohttp


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
