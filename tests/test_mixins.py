"""Tests for abstract methods in Mixin classes."""

import pytest

from openevsehttp.commands import CommandsMixin
from openevsehttp.managers import ManagersMixin
from openevsehttp.properties import PropertiesMixin
from openevsehttp.sensors import SensorsMixin

pytestmark = pytest.mark.asyncio


async def test_commands_mixin_not_implemented():
    """Test NotImplementedError in CommandsMixin."""
    mixin = CommandsMixin()
    with pytest.raises(NotImplementedError):
        mixin._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await mixin.process_request("url")
    with pytest.raises(NotImplementedError):
        await mixin.send_command("cmd")
    with pytest.raises(NotImplementedError):
        await mixin.update()
    with pytest.raises(NotImplementedError):
        mixin._normalize_response({})


async def test_managers_mixin_not_implemented():
    """Test NotImplementedError in ManagersMixin."""
    mixin = ManagersMixin()
    with pytest.raises(NotImplementedError):
        mixin._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await mixin.process_request("url")
    with pytest.raises(NotImplementedError):
        mixin._normalize_response({})


async def test_sensors_mixin_not_implemented():
    """Test NotImplementedError in SensorsMixin."""
    mixin = SensorsMixin()
    with pytest.raises(NotImplementedError):
        mixin._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await mixin.process_request("url")
    with pytest.raises(NotImplementedError):
        mixin._normalize_response({})


async def test_properties_mixin_not_implemented():
    """Test NotImplementedError in PropertiesMixin."""
    mixin = PropertiesMixin()
    with pytest.raises(NotImplementedError):
        mixin._version_check("1.0.0")
    with pytest.raises(NotImplementedError):
        await mixin.list_claims()
    with pytest.raises(NotImplementedError):
        await mixin.get_override()
