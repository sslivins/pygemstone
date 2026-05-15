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


@pytest.mark.rest
async def test_account_profile(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/account/profile",
            payload={
                "data": {
                    "id": "u-1",
                    "username": "Tester",
                    "email": "t@e.com",
                    "emailOptIn": False,
                    "cancelledDeletion": False,
                    "scannedDeviceIds": {},
                    "createdAt": 1700000000,
                    "lastUpdatedAt": 1700000001,
                },
                "statusCode": 200,
            },
        )
        profile = await gc.account_profile()
    assert profile.id == "u-1"
    assert profile.username == "Tester"


@pytest.mark.rest
async def test_homegroup_users(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/users?homegroupId=hg",
            payload={
                "data": [
                    {
                        "userId": "u-1",
                        "homegroupId": "hg",
                        "homegroupName": "Home",
                        "role": "homegroupOwner",
                        "invitationStatus": "approved",
                        "username": "Tester",
                        "email": "t@e.com",
                    }
                ],
                "statusCode": 200,
            },
        )
        users = await gc.homegroup_users("hg")
    assert len(users) == 1
    assert users[0].role == "homegroupOwner"


@pytest.mark.rest
async def test_invitations_raw(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/homegroup/invitation?invitationStatus=pending",
            payload={"data": [], "statusCode": 200},
        )
        assert await gc.invitations() == []


@pytest.mark.rest
async def test_device_groups_raw(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/deviceGroup/list?homegroupId=hg",
            payload={"data": [], "statusCode": 200},
        )
        assert await gc.device_groups("hg") == []


@pytest.mark.rest
async def test_folders(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/folders/list",
            payload={
                "data": [
                    {
                        "folderId": "f-1",
                        "name": "Custom",
                        "icon": "star",
                        "ownerId": "u-1",
                        "gemstoneManaged": False,
                        "backgroundColor": 100,
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                    }
                ],
                "statusCode": 200,
            },
        )
        folders = await gc.folders()
    assert len(folders) == 1
    assert folders[0].folder_id == "f-1"


@pytest.mark.rest
async def test_folder_patterns_pagination(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/folders/pattern/list?page=2",
            payload={
                "data": [
                    {
                        "id": "fp-1",
                        "folderId": "f-1",
                        "ownerId": "u-1",
                        "patternData": {
                            "id": "p-1",
                            "name": "Red",
                            "colors": [255],
                            "animation": "motionless",
                            "brightness": 255,
                            "speed": 128,
                            "direction": 0,
                            "backgroundColor": 0,
                            "referencePatternId": "p-1",
                        },
                        "isFavorite": False,
                    }
                ],
                "statusCode": 200,
            },
        )
        patterns = await gc.folder_patterns(page=2)
    assert len(patterns) == 1
    assert patterns[0].pattern.name == "Red"


@pytest.mark.rest
async def test_save_folder(gc: GemstoneClient) -> None:
    body = {
        "folderId": "f-1",
        "ownerId": "u-1",
        "name": "Renamed",
        "icon": "star",
        "backgroundColor": 100,
        "isSynchronized": True,
        "createdAt": 1700000000,
        "newFolder": False,
    }
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/folders/save?folderId=f-1",
            payload={"data": {**body, "lastUpdatedAt": 1700000005}, "statusCode": 200},
        )
        folder = await gc.save_folder("f-1", body)
    assert folder.folder_id == "f-1"
    assert folder.name == "Renamed"
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"] == body


@pytest.mark.rest
async def test_swatches(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/swatches/list",
            payload={
                "data": [
                    {
                        "id": "s-1",
                        "name": "Brights",
                        "ownerId": "owner",
                        "swatchesColorData": [
                            {"color": 255, "name": "Red"},
                            {"color": 65280, "name": "Green"},
                        ],
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                    }
                ],
                "statusCode": 200,
            },
        )
        swatches = await gc.swatches()
    assert len(swatches) == 1
    assert swatches[0].colors[1].name == "Green"


@pytest.mark.rest
async def test_downloadable_folders(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/downloads/folders/listGemstoneManaged?page=1",
            payload={
                "data": [
                    {
                        "id": "df-1",
                        "name": "Easter",
                        "folderName": "Easter",
                        "icon": "rabbit_face",
                        "category": "holidays",
                        "uploaderId": "gemstoneLightsOwned",
                        "downloads": 5,
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                        "approvedAt": 1700000002,
                    }
                ],
                "statusCode": 200,
            },
        )
        folders = await gc.downloadable_folders(page=1)
    assert folders[0].category == "holidays"


@pytest.mark.rest
async def test_downloadable_patterns(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/downloads/folders/pattern/listGemstoneManaged?page=3",
            payload={
                "data": [
                    {
                        "id": "dp-1",
                        "patternName": "Pop",
                        "category": "fun",
                        "uploaderId": "gemstoneLightsOwned",
                        "downloadableFolderId": "df-1",
                        "downloads": 0,
                        "patternData": {
                            "id": "dp-1",
                            "name": "Pop",
                            "colors": [255],
                            "animation": "chase",
                            "brightness": 255,
                            "speed": 128,
                            "direction": 0,
                            "backgroundColor": 0,
                            "referencePatternId": "dp-1",
                        },
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                        "approvedAt": 1700000002,
                    }
                ],
                "statusCode": 200,
            },
        )
        patterns = await gc.downloadable_patterns(page=3)
    assert patterns[0].pattern.animation == "chase"


@pytest.mark.rest
async def test_events_settings(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/events/settings?homegroupId=hg",
            payload={
                "data": {
                    "homegroupId": "hg",
                    "categoryIds": ["fun"],
                    "deviceIds": ["d-1"],
                    "setupYet": True,
                    "allowStaticPatterns": True,
                    "allowAnimatedPatterns": False,
                    "schedule": {
                        "onTime": "sunset",
                        "offTime": "22:00",
                        "onOffsetInMinutes": 0,
                        "offOffsetInMinutes": 0,
                    },
                    "createdAt": 1700000000,
                    "lastUpdatedAt": 1700000001,
                },
                "statusCode": 200,
            },
        )
        es = await gc.events_settings("hg")
    assert es.setup_yet is True
    assert es.allow_animated_patterns is False
    assert es.schedule is not None
    assert es.schedule.on_time == "sunset"


@pytest.mark.rest
async def test_subscribed_events(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/events/listSubscribed?homegroupId=hg&page=0",
            payload={
                "data": [
                    {
                        "eventId": "e-1",
                        "name": "Test Event",
                        "homegroupId": "hg",
                        "categoryId": "fun",
                        "categoryName": "Fun",
                        "icon": "party_popper",
                        "group": "general",
                        "yearMonthHalf": "2026051",
                        "startDate": "2026-05-01",
                        "endDate": "2026-05-02",
                        "staticPatterns": [],
                        "animatedPatterns": [],
                    }
                ],
                "statusCode": 200,
            },
        )
        events = await gc.subscribed_events("hg")
    assert events[0].event_id == "e-1"


@pytest.mark.rest
async def test_announcements(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/announcements",
            payload={
                "data": [
                    {
                        "id": "a-1",
                        "title": "Hello",
                        "descriptionText": "Welcome.",
                        "icon": "house_with_garden",
                        "startDate": "2025-01-01",
                        "endDate": "2025-12-31",
                        "roles": ["homegroupOwner"],
                    }
                ],
                "statusCode": 200,
            },
        )
        anns = await gc.announcements()
    assert anns[0].title == "Hello"
