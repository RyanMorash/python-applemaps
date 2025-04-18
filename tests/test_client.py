import pytest
from aioresponses import aioresponses
from apple_maps.client import AppleMapsApiClient, AppleMapsApiClientError, AppleMapsApiClientCommunicationError, AppleMapsApiClientAuthenticationError

@pytest.fixture
def client():
    return AppleMapsApiClient(
        key_id="test_key_id",
        service_id="test_service_id",
        team_id="test_team_id",
        key_pem="test_key_pem",
        session=None,
    )

@pytest.mark.asyncio
async def test_get_travel_time(client):
    with aioresponses() as m:
        m.get(
            "https://maps-api.apple.com/v1/etas?origin=37.7749,-122.4194&destination=34.0522,-118.2437&transportType=automobile",
            payload={"travelTime": 3600},
        )

        result = await client.get_travel_time(37.7749, -122.4194, 34.0522, -118.2437, "automobile")
        assert result["travelTime"] == 3600

@pytest.mark.asyncio
async def test_get_maps_access_token(client):
    with aioresponses() as m:
        m.post(
            "https://maps-api.apple.com/v1/token",
            payload={"access_token": "test_token", "expires_in": 3600},
        )

        result = await client.get_maps_access_token()
        assert result["access_token"] == "test_token"
        assert result["expires_in"] == 3600

@pytest.mark.asyncio
async def test_get_travel_time_authentication_error(client):
    with aioresponses() as m:
        m.get(
            "https://maps-api.apple.com/v1/etas?origin=37.7749,-122.4194&destination=34.0522,-118.2437&transportType=automobile",
            status=401,
            body="Invalid credentials",
        )

        with pytest.raises(AppleMapsApiClientAuthenticationError):
            await client.get_travel_time(37.7749, -122.4194, 34.0522, -118.2437, "automobile")

@pytest.mark.asyncio
async def test_get_travel_time_communication_error(client):
    with aioresponses() as m:
        m.get(
            "https://maps-api.apple.com/v1/etas?origin=37.7749,-122.4194&destination=34.0522,-118.2437&transportType=automobile",
            exception=Exception("Communication error"),
        )

        with pytest.raises(AppleMapsApiClientCommunicationError):
            await client.get_travel_time(37.7749, -122.4194, 34.0522, -118.2437, "automobile")
