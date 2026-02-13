"""Provide common pytest fixtures."""

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses

import openevsehttp.__main__ as main
from tests.common import load_fixture

TEST_URL_STATUS = "http://openevse.test.tld/status"
TEST_URL_CONFIG = "http://openevse.test.tld/config"
TEST_URL_RAPI = "http://openevse.test.tld/r"
TEST_URL_WS = "ws://openevse.test.tld/ws"
TEST_TLD = "openevse.test.tld"


@pytest_asyncio.fixture(
    params=[None, "external"],
    ids=["internal_session", "external_session"],
)
async def session(request):
    """Provide a session fixture that yields None (internal) or external session."""
    if request.param == "external":
        async with aiohttp.ClientSession() as session:
            yield session
    else:
        yield None


@pytest_asyncio.fixture
async def test_charger_auth(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword", session=session)


@pytest_asyncio.fixture
async def test_charger_auth_err(mock_aioclient, session):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        status=401,
    )
    mock_aioclient.get(
        TEST_URL_CONFIG,
        status=401,
    )
    return main.OpenEVSE(TEST_TLD, user="testuser", pwd="fakepassword", session=session)


@pytest_asyncio.fixture
async def test_charger(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_timeout(mock_aioclient, session):
    """Load the charger data."""
    mock_aioclient.get(
        TEST_URL_STATUS,
        exception=TimeoutError,
    )
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_dev(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_new(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_broken(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_broken_semver(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_unknown_semver(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_modified_ver(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def test_charger_v2(mock_aioclient, session):
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
    return main.OpenEVSE(TEST_TLD, session=session)


@pytest_asyncio.fixture
async def charger(request, mock_aioclient, session):
    """Fixture to create different charger types based on parameter.

    Use with indirect parametrization:
        @pytest.mark.parametrize("charger", ["test_charger", "test_charger_v2"], indirect=True)
    """
    charger_type = request.param

    if charger_type == "test_charger":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    elif charger_type == "test_charger_v2":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    elif charger_type == "test_charger_new":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    elif charger_type == "test_charger_broken":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    elif charger_type == "test_charger_dev":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    elif charger_type == "test_charger_broken_semver":
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
        return main.OpenEVSE(TEST_TLD, session=session)

    else:
        raise ValueError(f"Unknown charger type: {charger_type}")


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
