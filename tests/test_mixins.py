"""Tests for the Mixin classes to ensure 100% coverage."""

import pytest

from openevsehttp.commands import CommandsMixin
from openevsehttp.managers import ManagersMixin
from openevsehttp.properties import PropertiesMixin
from openevsehttp.sensors import SensorsMixin

# ruff: noqa: SLF001


class DummyCommands(CommandsMixin):
    """Dummy class for CommandsMixin tests."""

    def __init__(self):
        """Initialize dummy commands."""
        self.url = "http://test"
        self._status = {}
        self._config = {}
        self._session = None


class DummyManagers(ManagersMixin):
    """Dummy class for ManagersMixin tests."""

    def __init__(self):
        """Initialize dummy managers."""
        self.url = "http://test"


class DummyProperties(PropertiesMixin):
    """Dummy class for PropertiesMixin tests."""

    def __init__(self):
        """Initialize dummy properties."""
        self._status = {}
        self._config = {}


class DummySensors(SensorsMixin):
    """Dummy class for SensorsMixin tests."""

    def __init__(self):
        """Initialize dummy sensors."""
        self.url = "http://test"


def test_mixins_sync_not_implemented():
    """Test sync NotImplementedError in all mixins."""
    for cls in [DummyCommands, DummyManagers, DummyProperties, DummySensors]:
        obj = cls()
        with pytest.raises(NotImplementedError):
            obj._version_check("1.0.0")


@pytest.mark.asyncio
async def test_commands_mixin_async_not_implemented():
    """Test async NotImplementedError in CommandsMixin."""
    cmds = DummyCommands()
    with pytest.raises(NotImplementedError):
        await cmds.process_request("http://test")
    with pytest.raises(NotImplementedError):
        await cmds.send_command("test")
    with pytest.raises(NotImplementedError):
        await cmds.update()


@pytest.mark.asyncio
async def test_managers_mixin_not_implemented():
    """Test NotImplementedError in ManagersMixin."""
    mgrs = DummyManagers()
    with pytest.raises(NotImplementedError):
        await mgrs.process_request("http://test")


@pytest.mark.asyncio
async def test_properties_mixin_not_implemented():
    """Test NotImplementedError in PropertiesMixin."""
    props = DummyProperties()
    with pytest.raises(NotImplementedError):
        props._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await props.list_claims()
    with pytest.raises(NotImplementedError):
        await props.get_override()


@pytest.mark.asyncio
async def test_sensors_mixin_not_implemented():
    """Test NotImplementedError in SensorsMixin."""
    sensors = DummySensors()
    with pytest.raises(NotImplementedError):
        sensors._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await sensors.process_request("http://test")
