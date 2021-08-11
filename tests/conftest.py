"""Provide common pytest fixtures."""
import pytest

import openevsehttp
from tests.common import load_fixture


@pytest.fixture
def test_charger(status_mock, config_mock):
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
