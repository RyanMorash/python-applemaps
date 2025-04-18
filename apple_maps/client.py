from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime, timedelta
from typing import Any
from aiohttp_retry import RetryClient, ExponentialRetry

import aiohttp
import jwt


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
        self._access_token = None
        self._token_expires_at = None

    async def get_travel_time(
        self,
        originLat: float,
        originLon: float,
        destLat: float,
        destLon: float,
        transportType: str,
    ) -> Any:

        token = self._get_valid_access_token()

        return await self._api_wrapper(
            method="get",
            url=f"https://maps-api.apple.com/v1/etas?origin={originLat},{originLon}&destination={destLat},{destLon}&transportType={transportType}",
            headers={"Authorization": f"Bearer {token}"},
        )

    async def get_maps_access_token(self) -> dict:
        """Get a maps access token using JWT authentication."""
        token = self._generate_jwt()
        
        return await self._api_wrapper(
            method="post",
            url="https://maps-api.apple.com/v1/token",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"}
        )
    
    def _is_token_valid(self) -> bool:
        """Check if the current access token is valid and not expired."""
        if not self._access_token or not self._token_expires_at:
            return False
        # Add 30 second buffer before expiration
        return datetime.now(tz=UTC) < (self._token_expires_at - timedelta(seconds=30))
    
    async def _get_valid_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._is_token_valid():
            token_response = await self.get_maps_access_token()
            self._access_token = token_response["access_token"]
            self._token_expires_at = datetime.now(tz=UTC) + timedelta(seconds=token_response["expires_in"])
        return self._access_token

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
            async with asyncio.timeout(20):
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
