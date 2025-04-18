from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from aiohttp_retry import RetryClient, ExponentialRetry

import aiohttp
import async_timeout
import jwt

from . import DataSetType


class AppleMapsApiClientError(Exception):
    """Exception to indicate a general API error."""


class AppleMapsApiClientCommunicationError(AppleMapsApiClientError):
    """Exception to indicate a communication error."""


class AppleMapsApiClientAuthenticationError(AppleMapsApiClientError):
    """Exception to indicate an authentication error."""


class AppleMapsApiClient:
    def __init__(
        self,
        key_id: str,
        service_id: str,
        team_id: str,
        key_pem: str,
        session: aiohttp.ClientSession | None,
    ) -> None:
        self._key_id = key_id
        self._service_id = service_id
        self._team_id = team_id
        self._key_pem = key_pem
        self._session = session
        self._client = None # lazy loaded

    async def get_travel_time(
        self,
        originLat: float,
        originLon: float,
        destLat: float,
        destLon: float,
        transportType: str,
    ) -> Any:

        token = self._generate_jwt()

        return await self._api_wrapper(
            method="get",
            url=f"https://maps-api.apple.com/v1/etas?origin={originLat},{originLon}&destination={destLat},{destLon}&transportType={transportType}",
            headers={"Authorization": f"Bearer {token}"},
        )

    def _generate_jwt(self) -> str:
        return jwt.encode(
            {
                "iss": self._team_id,
                "iat": datetime.now(tz=UTC),
                "exp": datetime.now(tz=UTC) + timedelta(minutes=10),
                "sub": self._service_id,
            },
            self._key_pem,
            headers={"kid": self._key_id, "id": f"{self._team_id}.{self._service_id}"},
            algorithm="ES256",
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        if self._client is None:
            retry_options = ExponentialRetry(
                attempts=3,
                statuses=(404, 401, 403), # automatically includes any 5xx errors
                start_timeout=1,
            )
            self._client = RetryClient(retry_options=retry_options, client_session=self._session)

        try:
            async with async_timeout.timeout(20):
                response = await self._client.request(
                    method=method,
                    url=url,
                    raise_for_status=True,
                    headers=headers,
                    json=data,
                )

                if response.status in (401, 403):
                    body = await response.text()
                    raise AppleMapsApiClientAuthenticationError(
                        f"Invalid credentials: {body}",
                    )

                response.raise_for_status()
                return await response.json()

        except AppleMapsApiClientAuthenticationError as exception:
            raise exception
        except asyncio.TimeoutError as exception:
            raise AppleMapsApiClientCommunicationError(
                f"Timeout error fetching information: {exception}",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise AppleMapsApiClientCommunicationError(
                f"Error fetching information: {exception}",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise AppleMapsApiClientError(
                f"An unexpected error occurred: {exception}"
            ) from exception
