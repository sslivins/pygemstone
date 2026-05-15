"""REST-client tests that mock the AWS endpoints with aioresponses."""

from __future__ import annotations

import time

import pytest
from aioresponses import aioresponses

from pygemstone.auth import TokenSet
from pygemstone.client import GemstoneClient
from pygemstone.const import REST_API_BASE
from pygemstone.errors import GemstoneApiError, GemstoneAuthError
from pygemstone.models import Pattern


@pytest.fixture
def fake_tokens() -> TokenSet:
    return TokenSet(
        access_token="ACCESS",
        id_token="ID",
        refresh_token="REFRESH",
        expires_at=time.time() + 3600,
    )


@pytest.fixture
async def gc(fake_tokens: TokenSet):
    """A GemstoneClient that pretends to have already logged in.

    We patch ``ensure_fresh`` so the test never tries to hit the real
    Cognito SRP flow.
    """
    async with GemstoneClient("test@example.com", "pw") as client:
        client.auth._tokens = fake_tokens

        async def _no_refresh():
            return fake_tokens

        client.auth.ensure_fresh = _no_refresh  # type: ignore[method-assign]
        yield client


@pytest.mark.rest
async def test_homegroups(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/list",
            payload={
                "data": [
                    {
                        "id": "abc",
                        "name": "Home",
                        "role": "homegroupOwner",
                        "scannedDeviceIds": {},
                        "homegroupUserIds": [],
                        "createdAt": 1700000000,
                    }
                ],
                "statusCode": 200,
            },
        )
        groups = await gc.homegroups()
    assert len(groups) == 1
    assert groups[0].id == "abc"
    assert groups[0].name == "Home"


@pytest.mark.rest
async def test_devices_with_explicit_homegroup(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/devices?homegroupId=hg",
            payload={
                "data": [
                    {
                        "id": "h2-test",
                        "name": "Front Yard",
                        "homegroupId": "hg",
                        "firmware": "1.1.0",
                    }
                ],
                "statusCode": 200,
            },
        )
        devices = await gc.devices("hg")
    assert len(devices) == 1
    assert devices[0].id == "h2-test"
    assert devices[0].firmware == "1.1.0"


@pytest.mark.rest
async def test_set_on_state(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/onState?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-1234"}, "statusCode": 200},
        )
        tx = await gc.set_on_state("h2-test", True)
    assert tx == "tx-1234"

    # Verify the body we sent
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"] == {"onState": True}


@pytest.mark.rest
async def test_play_pattern(gc: GemstoneClient) -> None:
    pat = Pattern(
        id="pat-1",
        name="Test Pattern",
        colors=[255, 0, 0, 0],
        animation="motionless",
        brightness=200,
        speed=128,
        direction=0,
        background_color=0,
        reference_pattern_id="ref-1",
    )
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/play/pattern?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-9999"}, "statusCode": 200},
        )
        tx = await gc.play_pattern("h2-test", pat)
    assert tx == "tx-9999"
    req = next(iter(m.requests.values()))[0]
    body = req.kwargs["json"]
    assert body["pattern"]["name"] == "Test Pattern"
    assert body["pattern"]["brightness"] == 200


@pytest.mark.rest
async def test_401_is_auth_error(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/list",
            status=401,
            body='{"message":"Unauthorized"}',
        )
        with pytest.raises(GemstoneAuthError):
            await gc.homegroups()


@pytest.mark.rest
async def test_500_is_api_error(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/list",
            status=500,
            body="internal error",
        )
        with pytest.raises(GemstoneApiError) as ei:
            await gc.homegroups()
    assert ei.value.status == 500
