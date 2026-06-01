"""Provide common pytest fixtures."""

import json
from typing import Any, NamedTuple
from unittest.mock import patch

import aiohttp
import pytest
from multidict import CIMultiDict

import openevsehttp as main
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


@pytest.fixture(name="test_charger_v4_0")
def test_charger_v4_0(mock_aioclient):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=200,
        body=load_fixture("v4_json/status.json"),
    )
    # Load and modify config for v4.0.0
    config = json.loads(load_fixture("v4_json/config.json"))
    config["version"] = "4.0.0"
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=200,
        body=json.dumps(config),
    )
    return main.OpenEVSE(TEST_TLD)


class MockResponse:
    def __init__(
        self,
        method: str,
        url: str,
        status: int,
        body: Any,
        headers: dict | None,
        content_type: str,
    ):
        self.method = method
        self.url = url
        self.status = status
        self._body = body
        self.headers = CIMultiDict(headers or {})
        if content_type:
            self.headers.setdefault("content-type", content_type)

    async def text(self, encoding: str | None = None, errors: str = "strict") -> str:
        if isinstance(self._body, bytes):
            return self._body.decode(encoding or "utf-8", errors=errors)
        if isinstance(self._body, str):
            return self._body

        return json.dumps(self._body)

    async def read(self) -> bytes:
        if isinstance(self._body, bytes):
            return self._body
        if isinstance(self._body, str):
            return self._body.encode("utf-8")

        return json.dumps(self._body).encode("utf-8")

    async def json(self, *args, **kwargs) -> Any:
        if isinstance(self._body, bytes):
            return json.loads(self._body.decode("utf-8"))
        if isinstance(self._body, str):
            return json.loads(self._body)
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class RegisteredMock(NamedTuple):
    method: str
    url_pattern: Any
    status: int
    body: Any
    exception: Any
    repeat: bool
    content_type: str
    headers: dict | None


class AiohttpClientMocker:
    def __init__(self):
        self.mocks = []
        self._patcher = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._patcher = patch.object(
            aiohttp.ClientSession, "_request", new=self._request_mock
        )
        self._patcher.start()

    def stop(self):
        if self._patcher:
            self._patcher.stop()

    def add(
        self,
        method: str,
        url: Any,
        status: int = 200,
        body: Any = "",
        exception: Any = None,
        repeat: bool = False,
        content_type: str = "application/json",
        headers: dict | None = None,
    ):
        self.mocks.append(
            RegisteredMock(
                method=method.upper(),
                url_pattern=url,
                status=status,
                body=body,
                exception=exception,
                repeat=repeat,
                content_type=content_type,
                headers=headers,
            )
        )

    def get(self, *args, **kwargs):
        self.add("GET", *args, **kwargs)

    def post(self, *args, **kwargs):
        self.add("POST", *args, **kwargs)

    def put(self, *args, **kwargs):
        self.add("PUT", *args, **kwargs)

    def delete(self, *args, **kwargs):
        self.add("DELETE", *args, **kwargs)

    def patch(self, *args, **kwargs):
        self.add("PATCH", *args, **kwargs)

    def head(self, *args, **kwargs):
        self.add("HEAD", *args, **kwargs)

    def options(self, *args, **kwargs):
        self.add("OPTIONS", *args, **kwargs)

    async def _request_mock(self, method: str, str_or_url: Any, **kwargs: Any):
        url_str = str(str_or_url)
        method_upper = method.upper()

        matching_mock = None
        matching_index = -1

        for i, mock in enumerate(self.mocks):
            if mock.method != method_upper:
                continue
            matched = False
            if hasattr(mock.url_pattern, "match"):
                if mock.url_pattern.match(url_str):
                    matched = True
            elif isinstance(mock.url_pattern, str):
                if mock.url_pattern == url_str:
                    matched = True

            if matched:
                matching_mock = mock
                matching_index = i
                break

        if not matching_mock:
            raise AssertionError(f"No mock registered for {method_upper} {url_str}")

        if not matching_mock.repeat:
            self.mocks.pop(matching_index)

        if matching_mock.exception:
            raise matching_mock.exception

        return MockResponse(
            method=method_upper,
            url=url_str,
            status=matching_mock.status,
            body=matching_mock.body,
            headers=matching_mock.headers,
            content_type=matching_mock.content_type,
        )


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with AiohttpClientMocker() as mock_aiohttp:
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
    with AiohttpClientMocker() as m:
        yield m
