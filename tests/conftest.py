"""Provide common pytest fixtures."""
import pytest
import json

import openevsehttp
from tests.common import load_fixture


@pytest.fixture(name="test_charger_auth")
def test_charger_auth(status_mock, config_mock):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(
        "openevse.test.tld", user="testuser", pwd="fakepassword"
    )


@pytest.fixture(name="test_charger_auth_err")
def test_charger_auth_err(status_mock_err, config_mock_err):
    """Load the charger data."""
    return openevsehttp.OpenEVSE(
        "openevse.test.tld", user="testuser", pwd="fakepassword"
    )


@pytest.fixture(name="status_mock_err")
def mock_status_err(requests_mock):
    """Mock the status reply."""
    requests_mock.get(
        "http://openevse.test.tld/status",
        status_code=401,
    )


@pytest.fixture(name="config_mock_err")
def mock_config_err(requests_mock):
    """Mock the config reply."""
    requests_mock.get(
        "http://openevse.test.tld/config",
        status_code=401,
    )


@pytest.fixture(name="test_charger")
def test_charger(status_mock, config_mock):
    """Load the charger data."""
    return openevsehttp.OpenEVSE("openevse.test.tld")


@pytest.fixture(name="test_charger_v2")
def test_charger_v2(status_mock_v2, config_mock_v2):
    """Load the charger data."""
    return openevsehttp.OpenEVSE("openevse.test.tld")


@pytest.fixture(name="status_mock")
def mock_status(requests_mock):
    """Mock the status reply."""
    requests_mock.get(
        "http://openevse.test.tld/status",
        text=load_fixture("v4_json/status.json"),
    )


@pytest.fixture(name="config_mock")
def mock_config(requests_mock):
    """Mock the config reply."""
    requests_mock.get(
        "http://openevse.test.tld/config",
        text=load_fixture("v4_json/config.json"),
    )


@pytest.fixture(name="status_mock_v2")
def mock_status_v2(requests_mock):
    """Mock the status reply."""
    requests_mock.get(
        "http://openevse.test.tld/status",
        text=load_fixture("v2_json/status.json"),
    )


@pytest.fixture(name="config_mock_v2")
def mock_config_v2(requests_mock):
    """Mock the config reply."""
    requests_mock.get(
        "http://openevse.test.tld/config",
        text=load_fixture("v2_json/config.json"),
    )


@pytest.fixture(name="send_command_mock")
def mock_send_command(requests_mock):
    """Mock the command reply."""
    value = {"cmd": "OK", "ret": "$OK^20"}
    requests_mock.post(
        "http://openevse.test.tld/r",
        text=json.dumps(value),
    )


@pytest.fixture(name="send_command_parse_err")
def mock_send_command_parse_err(requests_mock):
    """Mock the command reply parse err."""
    requests_mock.post(
        "http://openevse.test.tld/r",
        status_code=400,
    )


@pytest.fixture(name="send_command_auth_err")
def mock_send_command_auth_err(requests_mock):
    """Mock the command reply auth err."""
    requests_mock.post(
        "http://openevse.test.tld/r",
        status_code=401,
    )


@pytest.fixture(name="send_command_mock_missing")
def mock_send_command_missing(requests_mock):
    """Mock the command reply."""
    value = {"cmd": "OK", "what": "$NK^21"}
    requests_mock.post(
        "http://openevse.test.tld/r",
        text=json.dumps(value),
    )


@pytest.fixture(name="send_command_mock_failed")
def mock_send_command_failed(requests_mock):
    """Mock the command reply."""
    value = {"cmd": "OK", "ret": "$NK^21"}
    requests_mock.post(
        "http://openevse.test.tld/r",
        text=json.dumps(value),
    )