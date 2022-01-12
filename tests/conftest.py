"""Provide common pytest fixtures."""
import json

import pytest
from aioresponses import aioresponses

import openevsehttp
from tests.common import load_fixture

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_RAPI = "http://openevse.test.tld/r"
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
    return openevsehttp.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


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
    return openevsehttp.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


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
    return openevsehttp.OpenEVSE(TEST_TLD)


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
    return openevsehttp.OpenEVSE(TEST_TLD)


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
