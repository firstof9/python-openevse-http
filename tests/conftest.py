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


def _setup_charger(
    mock_aioclient,
    status_fixture="v4_json/status.json",
    config_fixture="v4_json/config.json",
    ws_fixture="v4_json/status.json",
    user=None,
    pwd=None,
    status_code=200,
    config_code=200,
    is_ws=True,
    version_override=None,
    status_exception=None,
):
    """Set up mocked endpoints and return an OpenEVSE client."""
    if status_exception:
        mock_aioclient.get(
            TEST_URL_STATUS,
            exception=status_exception,
        )
    elif status_fixture:
        mock_aioclient.get(
            TEST_URL_STATUS,
            status=status_code,
            body=load_fixture(status_fixture) if status_code == 200 else "",
        )

    if config_fixture:
        if version_override:
            config = json.loads(load_fixture(config_fixture))
            config["version"] = version_override
            body = json.dumps(config)
        else:
            body = load_fixture(config_fixture) if config_code == 200 else ""
        mock_aioclient.get(
            TEST_URL_CONFIG,
            status=config_code,
            body=body,
        )

    if is_ws and ws_fixture:
        mock_aioclient.get(
            TEST_URL_WS,
            status=200,
            body=load_fixture(ws_fixture),
            repeat=True,
        )

    return main.OpenEVSE(TEST_TLD, user=user, pwd=pwd)


@pytest.fixture(name="test_charger_auth")
def test_charger_auth(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(mock_aioclient, user="testuser", pwd="fakepassword")


@pytest.fixture(name="test_charger_auth_err")
def test_charger_auth_err(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient,
        status_code=401,
        config_code=401,
        is_ws=False,
        user="testuser",
        pwd="fakepassword",
    )


@pytest.fixture(name="test_charger")
def test_charger(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(mock_aioclient)


@pytest.fixture(name="test_charger_timeout")
def test_charger_timeout(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient, status_exception=TimeoutError, config_fixture=None, is_ws=False
    )


@pytest.fixture(name="test_charger_dev")
def test_charger_dev(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(mock_aioclient, config_fixture="v4_json/config-dev.json")


@pytest.fixture(name="test_charger_new")
def test_charger_new(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient,
        status_fixture="v4_json/status-new.json",
        config_fixture="v4_json/config-new.json",
        ws_fixture="v4_json/status-new.json",
    )


@pytest.fixture(name="test_charger_broken")
def test_charger_broken(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient,
        status_fixture="v4_json/status-broken.json",
        config_fixture="v4_json/config-broken.json",
        is_ws=False,
    )


@pytest.fixture(name="test_charger_broken_semver")
def test_charger_broken_semver(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient, config_fixture="v4_json/config-broken-semver.json", is_ws=False
    )


@pytest.fixture(name="test_charger_unknown_semver")
def test_charger_unknown_semver(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient, config_fixture="v4_json/config-unknown-semver.json", is_ws=False
    )


@pytest.fixture(name="test_charger_modified_ver")
def test_charger_modified_ver(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient, config_fixture="v4_json/config-extra-version.json", is_ws=False
    )


@pytest.fixture(name="test_charger_v2")
def test_charger_v2(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(
        mock_aioclient,
        status_fixture="v2_json/status.json",
        config_fixture="v2_json/config.json",
        is_ws=False,
    )


@pytest.fixture(name="test_charger_v4_0")
def test_charger_v4_0(mock_aioclient):
    """Load the charger data."""
    return _setup_charger(mock_aioclient, version_override="4.0.0", is_ws=False)


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
        self.requests = []
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
        self.requests.append((method_upper, url_str, kwargs))

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
