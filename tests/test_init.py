import pytest


def test_get_status(http_mock_status, http_mock_config, test_charger):
    """Test v4 Status reply"""
    status = test_charger.status
    assert status == "sleeping"
