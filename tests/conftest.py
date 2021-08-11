import pytest
import openevsehttp
import requests_mock
from tests.common import load_fixture


@pytest.fixture
def test_charger(status_mock, config_mock):
    return openevsehttp.OpenEVSE("openevse.test.tld")


@pytest.fixture(name="status_mock")
def mock_status(requests_mock):
    requests_mock.get(
        "http://openevse.test.tld/status",
        text=load_fixture("v4_json/status.json"),
    )


@pytest.fixture(name="config_mock")
def mock_config(requests_mock):
    requests_mock.get(
        "http://openevse.test.tld/config",
        text=load_fixture("v4_json/config.json"),
    )
