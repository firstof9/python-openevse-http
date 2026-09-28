"""Base mixin providing protocol stubs and common helpers for command mixins."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class BaseCommandMixin:
    """Base mixin defining internal attributes and stub methods required by command mixins."""

    url: str
    ssl: bool
    ssl_verify: bool
    _status: dict[str, Any]
    _config: dict[str, Any]
    _session: aiohttp.ClientSession | None
    _github_token: str | None

    # These are implemented in OpenEVSE (client.py)
    def _version_check(self, min_version: str, max_version: str = "") -> bool:
        raise NotImplementedError

    def _controller_version_check(
        self, min_version: str, max_version: str = ""
    ) -> bool:
        raise NotImplementedError

    def _require_firmware(
        self, min_version: str, feature: str, max_version: str = ""
    ) -> None:
        raise NotImplementedError

    def _require_controller_firmware(
        self, min_version: str, feature: str, max_version: str = ""
    ) -> None:
        raise NotImplementedError

    async def process_request(
        self,
        url: str,
        method: str = "",
        data: Any = None,
        rapi: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Mapping[str, Any] | list[Any] | str | bool:
        raise NotImplementedError

    async def send_command(self, command: str) -> tuple[Any, Any]:
        raise NotImplementedError

    async def update(self, force_status: bool = False) -> None:
        raise NotImplementedError

    def _normalize_response(self, response: Any) -> dict[str, Any] | list[Any]:
        """Normalize response to a dict or list."""
        raise NotImplementedError

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the configured HTTP session."""
        raise NotImplementedError
