"""Provide common pytest fixtures."""
import pytest

import openevsehttp
from tests.common import load_fixture


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