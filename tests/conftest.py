"""Provide common pytest fixtures."""
import pytest
import json

import openevsehttp
from tests.common import load_fixture

from aioresponses import aioresponses

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_TLD = "openevse.test.tld"


@pytest.fixture(name="test_charger_auth")
def test_charger_auth(status_mock, config_mock):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


@pytest.fixture(name="test_charger_auth_err")
def test_charger_auth_err(status_mock_err, config_mock_err):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword")


@pytest.fixture(name="status_mock_err")
def mock_status_err():
    """Mock the status reply."""
    with aioresponses() as client_mock:
        client_mock.get(
            TEST_URL_STATUS,
            status=401,
        )

        yield client_mock


@pytest.fixture(name="config_mock_err")
def mock_config_err():
    """Mock the config reply."""
    with aioresponses() as client_mock:
        client_mock.get(
            TEST_URL_CONFIG,
            status=401,
        )

        yield client_mock


@pytest.fixture(name="test_charger")
def test_charger(status_mock, config_mock):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(TEST_TLD)


@pytest.fixture(name="test_charger_v2")
def test_charger_v2(status_mock_v2, config_mock_v2):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(TEST_TLD)


@pytest.fixture(name="status_mock")
def mock_status():
    """Mock the status reply."""
    with aioresponses() as mock_status:
        mock_status.get(
            TEST_URL_STATUS,
            status=200,
            body=load_fixture("v4_json/status.json"),
        )

        yield mock_status


@pytest.fixture(name="config_mock")
def mock_config():
    """Mock the config reply."""
    with aioresponses() as mock_config:
        mock_config.get(
            TEST_URL_CONFIG,
            status=200,
            body=load_fixture("v4_json/config.json"),
        )

        yield mock_config


@pytest.fixture(name="status_mock_v2")
def mock_status_v2():
    """Mock the status reply."""
    with aioresponses() as client_mock:
        client_mock.get(
            TEST_URL_STATUS,
            status=200,
            body=load_fixture("v2_json/status.json"),
        )
        yield client_mock


@pytest.fixture(name="config_mock_v2")
def mock_config_v2():
    """Mock the config reply."""
    with aioresponses() as client_mock:
        client_mock.get(
            TEST_URL_CONFIG,
            status=200,
            body=load_fixture("v2_json/config.json"),
        )
        yield client_mock


@pytest.fixture(name="send_command_mock")
def mock_send_command():
    """Mock the command reply."""
    with aioresponses() as client_mock:
        value = {"cmd": "OK", "ret": "$OK^20"}
        client_mock.post(
            TEST_URL_RAPI,
            status=200,
            body=json.dumps(value),
        )
        yield client_mock


@pytest.fixture(name="send_command_parse_err")
def mock_send_command_parse_err():
    """Mock the command reply parse err."""
    with aioresponses() as client_mock:
        client_mock.post(
            TEST_URL_RAPI,
            status=400,
        )
        yield client_mock


@pytest.fixture(name="send_command_auth_err")
def mock_send_command_auth_err():
    """Mock the command reply auth err."""
    with aioresponses() as client_mock:
        client_mock.post(
            TEST_URL_RAPI,
            status=401,
        )
        yield client_mock


@pytest.fixture(name="send_command_mock_missing")
def mock_send_command_missing():
    """Mock the command reply."""
    with aioresponses() as client_mock:
        value = {"cmd": "OK", "what": "$NK^21"}
        client_mock.post(
            TEST_URL_RAPI,
            status=200,
            body=json.dumps(value),
        )
        yield client_mock


@pytest.fixture(name="send_command_mock_failed")
def mock_send_command_failed():
    """Mock the command reply."""
    with aioresponses() as client_mock:
        value = {"cmd": "OK", "ret": "$NK^21"}
        client_mock.post(
            TEST_URL_RAPI,
            status=200,
            body=json.dumps(value),
        )
        yield client_mock


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
