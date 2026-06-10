"""Utility functions for python-openevse-http."""

import logging
import re

from awesomeversion import AwesomeVersion

_LOGGER = logging.getLogger(__name__)


def normalize_version(version: str) -> str:
    """Normalize the version string to strip 'dev' tag."""
    if "dev" in version:
        _LOGGER.debug("Stripping 'dev' from version.")
        value = version.split(".")
        return ".".join(value[0:3])
    return version


def get_awesome_version(version: str) -> AwesomeVersion:
    """Parse and normalize the version string, returning an AwesomeVersion."""
    # Match non-numeric git branch names (e.g. 'main', 'master', 'develop', or 'feature-x_abc123456')
    if (
        "master" in version
        or "main" in version
        or re.search(r"_[a-f0-9]{6,40}$", version)
    ):
        version = "dev"
    value = normalize_version(version)
    if "dev" not in version:
        firmware_search = re.search(r"\d+\.\d+\.\d+", value)
        if firmware_search:
            value = firmware_search.group(0)
    return AwesomeVersion(value)
