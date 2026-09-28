"""Security commands mixin for OpenEVSE."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .commands_base import BaseCommandMixin
from .const import SUCCESS_ANSWERS
from .exceptions import CommandFailedError

_LOGGER = logging.getLogger(__name__)


class SecurityCommandsMixin(BaseCommandMixin):
    """Mixin for OpenEVSE security commands (certificates and RFID)."""

    async def set_rfid_enabled(self, enable: bool = True) -> None:
        """Enable or disable RFID access."""
        self._require_firmware("4.1.4", "set_rfid_enabled")

        if not isinstance(enable, bool):
            raise TypeError("Value must be a boolean.")

        url = f"{self.url}config"
        data = {"rfid_enabled": enable}

        _LOGGER.debug("Setting rfid_enabled to %s", enable)
        response = await self.process_request(url=url, method="post", data=data)
        response = self._normalize_response(response)
        msg = response.get("msg") if isinstance(response, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem issuing command: %s", response)
            raise CommandFailedError(f"Problem issuing command: {response}")

        self._config["rfid_enabled"] = enable

    async def get_certificates(
        self, certificate_id: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Retrieve installed certificates or a specific certificate by hex ID.

        When certificate_id is None, queries 'GET /certificates' and returns a list
        of installed certificate dictionaries.
        When certificate_id is specified, queries 'GET /certificates/{certificate_id}'
        and returns the specific certificate dictionary.

        Requires gateway firmware 4.0.0 or higher.

        :param certificate_id: Hexadecimal certificate ID string, or None for all.
        :return: List of certificate dicts or single certificate dict.
        """
        self._require_firmware("4.0.0", "get_certificates")

        if certificate_id is not None:
            if not isinstance(certificate_id, str) or not certificate_id.strip():
                raise TypeError("certificate_id must be a non-empty string.")
            clean_id = certificate_id.strip()
            url = f"{self.url}certificates/{clean_id}"
        else:
            url = f"{self.url}certificates"

        _LOGGER.debug("Querying certificates: %s", url)
        response = await self.process_request(url=url, method="get")

        if certificate_id is not None:
            if not isinstance(response, Mapping):
                _LOGGER.error(
                    "Invalid response from /certificates/%s: %s", clean_id, response
                )
                raise CommandFailedError(
                    f"Invalid response from /certificates/{clean_id}: {response}"
                )
            return dict(response)

        if not isinstance(response, list):
            _LOGGER.error("Invalid response from /certificates: %s", response)
            raise CommandFailedError(f"Invalid response from /certificates: {response}")

        return [dict(item) for item in response if isinstance(item, Mapping)]

    async def get_root_ca(self) -> str:
        """Retrieve the concatenated root CA bundle as text.

        Queries 'GET /certificates/root'.

        Requires gateway firmware 4.0.0 or higher.

        :return: Root CA certificate bundle in PEM text format.
        """
        self._require_firmware("4.0.0", "get_root_ca")

        url = f"{self.url}certificates/root"
        _LOGGER.debug("Querying root CA certificates: %s", url)
        response = await self.process_request(url=url, method="get")
        if not isinstance(response, str):
            _LOGGER.error("Invalid response from /certificates/root: %s", response)
            raise CommandFailedError(
                f"Invalid response from /certificates/root: {response}"
            )
        return response

    async def add_certificate(
        self, name: str, certificate: str, key: str | None = None
    ) -> dict[str, Any]:
        """Add a certificate to the charger's certificate manager.

        Sends 'POST /certificates' with JSON payload.
        To install a Root CA, provide name and certificate.
        To install a client certificate, provide name, certificate, and private key.

        Requires gateway firmware 4.0.0 or higher.

        :param name: Friendly name for the certificate.
        :param certificate: PEM-encoded certificate string.
        :param key: Optional PEM-encoded private key string (for client certs).
        :return: Response dict containing 'id' and 'msg'.
        """
        self._require_firmware("4.0.0", "add_certificate")

        if not isinstance(name, str) or not name.strip():
            raise TypeError("name must be a non-empty string.")
        if not isinstance(certificate, str) or not certificate.strip():
            raise TypeError("certificate must be a non-empty string.")
        if key is not None and (not isinstance(key, str) or not key.strip()):
            raise TypeError("key must be a non-empty string or None.")

        url = f"{self.url}certificates"
        data: dict[str, Any] = {
            "name": name.strip(),
            "certificate": certificate,
        }
        if key is not None:
            data["key"] = key

        _LOGGER.debug("Adding certificate '%s'", name)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem adding certificate: %s", response)
            raise CommandFailedError(f"Problem adding certificate: {response}")

        return dict(normalized)

    async def delete_certificate(self, certificate_id: str) -> None:
        """Delete a certificate by hexadecimal ID.

        Sends 'DELETE /certificates/{certificate_id}'.

        Requires gateway firmware 4.0.0 or higher.

        :param certificate_id: Hexadecimal certificate ID string.
        """
        self._require_firmware("4.0.0", "delete_certificate")

        if not isinstance(certificate_id, str) or not certificate_id.strip():
            raise TypeError("certificate_id must be a non-empty string.")

        clean_id = certificate_id.strip()
        url = f"{self.url}certificates/{clean_id}"

        _LOGGER.debug("Deleting certificate %s", url)
        response = await self.process_request(url=url, method="delete")
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem deleting certificate: %s", response)
            raise CommandFailedError(f"Problem deleting certificate: {response}")

    async def add_rfid_tag(self) -> None:
        """Put the charger into RFID learning/pairing mode to add the next scanned RFID tag.

        Sends 'POST /rfid/add'.

        Requires gateway firmware 4.0.0 or higher.
        """
        self._require_firmware("4.0.0", "add_rfid_tag")

        url = f"{self.url}rfid/add"
        _LOGGER.debug("Triggering RFID add tag mode: %s", url)
        response = await self.process_request(url=url, method="post", data={})
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem adding RFID tag: %s", response)
            raise CommandFailedError(f"Problem adding RFID tag: {response}")

    async def get_rfid_users(self) -> dict[str, str]:
        """Get the mapping of RFID tags to user names.

        Sends 'GET /rfid/users'.

        Requires gateway firmware 5.0.0 or higher.

        :return: Dictionary mapping RFID tag ID to user name string.
        """
        self._require_firmware("5.0.0", "get_rfid_users")

        url = f"{self.url}rfid/users"
        _LOGGER.debug("Fetching RFID users from %s", url)
        response = await self.process_request(url=url, method="get")
        if not isinstance(response, Mapping):
            _LOGGER.error("Invalid response format for /rfid/users: %s", response)
            raise CommandFailedError(
                f"Invalid response format for /rfid/users: {response}"
            )

        return {str(k): str(v) for k, v in response.items()}

    async def set_rfid_user(self, rfid: str, name: str) -> None:
        """Assign or update a user name for an RFID tag.

        Sends 'POST /rfid/users' with JSON body {"rfid": rfid, "name": name}.

        Requires gateway firmware 5.0.0 or higher.

        :param rfid: RFID tag ID string.
        :param name: Friendly user name string.
        """
        self._require_firmware("5.0.0", "set_rfid_user")

        if not isinstance(rfid, str) or not rfid.strip():
            raise TypeError("rfid must be a non-empty string.")
        if not isinstance(name, str) or not name.strip():
            raise TypeError("name must be a non-empty string.")

        clean_rfid = rfid.strip()
        clean_name = name.strip()
        url = f"{self.url}rfid/users"
        data = {"rfid": clean_rfid, "name": clean_name}

        _LOGGER.debug("Setting RFID user '%s' for tag '%s'", clean_name, clean_rfid)
        response = await self.process_request(url=url, method="post", data=data)
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem setting RFID user: %s", response)
            raise CommandFailedError(f"Problem setting RFID user: {response}")

    async def delete_rfid_user(self, rfid: str) -> None:
        """Delete an RFID tag to user name mapping.

        Sends 'DELETE /rfid/users?rfid={rfid}'.

        Requires gateway firmware 5.0.0 or higher.

        :param rfid: RFID tag ID string to delete.
        """
        self._require_firmware("5.0.0", "delete_rfid_user")

        if not isinstance(rfid, str) or not rfid.strip():
            raise TypeError("rfid must be a non-empty string.")

        clean_rfid = rfid.strip()
        url = f"{self.url}rfid/users?rfid={clean_rfid}"

        _LOGGER.debug("Deleting RFID user for tag '%s'", clean_rfid)
        response = await self.process_request(url=url, method="delete")
        normalized = self._normalize_response(response)
        msg = normalized.get("msg") if isinstance(normalized, Mapping) else None
        if msg not in SUCCESS_ANSWERS:
            _LOGGER.error("Problem deleting RFID user: %s", response)
            raise CommandFailedError(f"Problem deleting RFID user: {response}")
