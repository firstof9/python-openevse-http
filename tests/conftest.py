import pytest
import json
import openevsehttp
from aioresponses import aioresponses
from tests.common import load_fixture


@pytest.fixture
def test_charger():
    return openevsehttp.OpenEVSE("openevse.test.tld")


@pytest.fixture(name="v4_status", scope="session")
def v4_status_fixture():
    """Load the v4 status fixture data."""
    return json.loads(load_fixture("v4_json/status.json"))


@pytest.fixture(name="v4_config", scope="session")
def v4_config_fixture():
    """Load the v4 config fixture data."""
    return json.loads(load_fixture("v4_json/config.json"))


@pytest.fixture(name="v4_schedule", scope="session")
def v4_schedule_fixture():
    """Load the v4 schedule fixture data."""
    return json.loads(load_fixture("v4_json/schedule.json"))


@pytest.fixture(name="http_mock_status")
def aiohttp_mock_status():
    """Fixture to mock aioclient calls."""

    with aioresponses() as aiohttp_mock_status:
        mock_headers = {"content-type": "application/json"}
        aiohttp_mock_status.get(
            "http://openevse.test.tld/status",
            headers=mock_headers,
            status=200,
            body=str(load_fixture("v4_json/status.json")),
        )
        yield


@pytest.fixture(name="http_mock_config")
def aiohttp_mock_config():
    """Fixture to mock aioclient calls."""

    with aioresponses() as aiohttp_mock_config:
        mock_headers = {"content-type": "application/json"}
        aiohttp_mock_config.get(
            "http://openevse.test.tld/config",
            headers=mock_headers,
            status=200,
            body=str(load_fixture("v4_json/config.json")),
        )
        yield
