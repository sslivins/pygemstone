"""REST-client tests that mock the AWS endpoints with aioresponses."""

from __future__ import annotations

import re
import time
from typing import Any

import pytest
from aioresponses import aioresponses

from pygemstone.auth import TokenSet
from pygemstone.client import GemstoneClient
from pygemstone.const import REST_API_BASE
from pygemstone.errors import (
    GemstoneApiError,
    GemstoneAuthError,
    GemstoneTimeoutError,
)
from pygemstone.models import (
    ArchitecturalDesign,
    Pattern,
    StaticColorSegment,
    Timer,
)


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
async def test_architectural_designs(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/deviceControl/architectural/list?deviceId=h2-test",
            payload={
                "data": [
                    {
                        "id": "ad-1",
                        "deviceId": "h2-test",
                        "name": "Front Door",
                        "brightness": 255,
                        "staticColors": [
                            {"lights": [300, 300, 307], "color": 4294967295}
                        ],
                        "isFavorite": False,
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                    }
                ],
                "statusCode": 200,
            },
        )
        designs = await gc.architectural_designs("h2-test")
    assert len(designs) == 1
    assert designs[0].id == "ad-1"
    assert designs[0].name == "Front Door"
    assert designs[0].static_colors[0].color == 4294967295


@pytest.mark.rest
async def test_save_architectural_design(gc: GemstoneClient) -> None:
    design = ArchitecturalDesign(
        id="ad-1",
        device_id="h2-test",
        name="Front Door",
        brightness=255,
        static_colors=[StaticColorSegment(lights=[300, 300, 307], color=4294967295)],
        is_favorite=False,
    )
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/architectural/save?deviceId=h2-test",
            payload={
                "data": {
                    "id": "ad-1",
                    "deviceId": "h2-test",
                    "name": "Front Door",
                    "brightness": 255,
                    "staticColors": [
                        {"lights": [300, 300, 307], "color": 4294967295}
                    ],
                    "isFavorite": False,
                    "createdAt": 1700000005,
                    "lastUpdatedAt": 1700000005,
                },
                "statusCode": 200,
            },
        )
        saved = await gc.save_architectural_design(design)
    assert saved.id == "ad-1"
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"]["name"] == "Front Door"


@pytest.mark.rest
async def test_play_architectural_design(gc: GemstoneClient) -> None:
    design = ArchitecturalDesign(
        id="ad-1",
        device_id="h2-test",
        name="Front Door",
        brightness=255,
        static_colors=[StaticColorSegment(lights=[300, 300, 307], color=4294967295)],
        is_favorite=False,
    )
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/play/architectural?deviceId=h2-test",
            payload={"data": {"txId": "tx-arch-1"}, "statusCode": 200},
        )
        tx = await gc.play_architectural_design(design)
    assert tx == "tx-arch-1"
    req = next(iter(m.requests.values()))[0]
    body = req.kwargs["json"]
    arch = body["architectural"]
    assert arch["id"] == "ad-1"
    assert arch["name"] == "Front Door"
    assert arch["preview"] is False
    assert arch["staticColors"] == [{"lights": [300, 300, 307], "color": 4294967295}]
    assert "deviceId" not in arch
    assert "isFavorite" not in arch


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


@pytest.mark.rest
async def test_timers_by_homegroup(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/timer/listByHomegroup?homegroupId=hg",
            payload={
                "data": [
                    {
                        "id": "t-1",
                        "name": "Front",
                        "homegroupId": "hg",
                        "assigneeId": "h2-test",
                        "enabled": True,
                        "timerData": {
                            "timerType": "daily",
                            "onTime": "sunset",
                            "offTime": "23:00",
                        },
                        "timerPatternData": {
                            "pattern": {
                                "id": "p-1",
                                "name": "Red",
                                "colors": [255],
                                "animation": "motionless",
                                "brightness": 255,
                                "speed": 128,
                                "direction": 0,
                                "backgroundColor": 0,
                                "referencePatternId": "p-1",
                            }
                        },
                        "txId": "tx-1",
                        "createdAt": 1700000000,
                        "lastUpdatedAt": 1700000001,
                    }
                ],
                "message": "Successful.",
                "statusCode": 200,
            },
        )
        timers = await gc.timers_by_homegroup("hg")
    assert len(timers) == 1
    assert timers[0].name == "Front"
    assert timers[0].timer_data is not None
    assert timers[0].timer_data.on_time == "sunset"
    assert timers[0].pattern is not None
    assert timers[0].pattern.name == "Red"


@pytest.mark.rest
async def test_events_categories(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/events/listCategories",
            payload={
                "data": [
                    {
                        "id": "christmas",
                        "name": "Christmas",
                        "description": "Festive patterns.",
                        "group": "general",
                        "icon": "christmas_tree",
                        "backgroundColor": 4294115301,
                        "suggested": True,
                    },
                    {
                        "id": "anaheim-ducks",
                        "name": "Anaheim Ducks",
                        "description": "Anaheim Ducks in NHL",
                        "group": "nhl",
                    },
                ],
                "statusCode": 200,
            },
        )
        cats = await gc.events_categories()
    assert len(cats) == 2
    assert cats[0].suggested is True
    assert cats[1].icon is None
    assert cats[1].background_color is None


# ---------------------------------------------------------------------------
# Write endpoints captured 2026-11-21 (zones, timers, patterns, arch CRUD)
# ---------------------------------------------------------------------------

from pygemstone.models import Zone


def _req(m: aioresponses, method: str):
    for (meth, url), calls in m.requests.items():
        if meth == method:
            return url, calls[0]
    raise AssertionError(f"no {method} request")


@pytest.mark.rest
async def test_zones_list_save_delete(gc: GemstoneClient) -> None:
    zone_payload = {
        "id": "z1", "deviceId": "h2-test", "name": "Door",
        "lights": [0, 0, 3], "icon": "house_3", "confirmed": False,
    }
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/deviceControl/zone/list?deviceId=h2-test",
            payload={"data": [zone_payload]},
        )
        m.put(
            f"{REST_API_BASE}/deviceControl/zone/save?deviceId=h2-test",
            payload={"data": {**zone_payload, "id": "ignored-echo"}},
        )
        m.delete(
            f"{REST_API_BASE}/deviceControl/zone/delete?deviceId=h2-test&zoneId=z1",
            payload={"message": "Zone deleted successfully"},
        )
        zones = await gc.zones("h2-test")
        new = Zone(id="", device_id="h2-test", name="Door", lights=[0, 0, 3])
        await gc.save_zone(new)
        await gc.delete_zone("h2-test", "z1")
    assert zones[0].indices == [0, 1, 2, 3]
    _, put = _req(m, "PUT")
    body = put.kwargs["json"]
    assert body["id"] and body["id"] == new.id  # client-generated uuid
    assert body["lights"] == [0, 0, 3]
    assert body["deviceId"] == "h2-test"


@pytest.mark.rest
async def test_impulse(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/play/impulse?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-i"}},
        )
        tx = await gc.impulse("h2-test", [1])
    assert tx == "tx-i"
    _, put = _req(m, "PUT")
    assert put.kwargs["json"] == {
        "impulse": {"lengthInSeconds": 0, "blinkPeriodMs": 0, "lights": [1], "color": 0}
    }


@pytest.mark.rest
async def test_architectural_delete_and_preview(gc: GemstoneClient) -> None:
    design = ArchitecturalDesign(
        id="ad-1", device_id="h2-test", name="Front Door", brightness=200,
        static_colors=[StaticColorSegment(lights=[0, 0, 7], color=255)],
        is_favorite=False,
    )
    with aioresponses() as m:
        m.delete(
            f"{REST_API_BASE}/deviceControl/architectural/delete"
            "?deviceId=h2-test&architecturalId=ad-1",
            payload={"statusCode": 200},
        )
        m.put(
            f"{REST_API_BASE}/deviceControl/play/architectural?deviceId=h2-test",
            payload={"data": {"txId": "tx-p"}},
        )
        await gc.delete_architectural_design("h2-test", "ad-1")
        tx = await gc.preview_architectural_design(design)
    assert tx == "tx-p"
    _, put = _req(m, "PUT")
    arch = put.kwargs["json"]["architectural"]
    assert arch["preview"] is True
    assert arch["name"] == "Preview"
    assert design.name == "Front Door"  # caller's object untouched


@pytest.mark.rest
async def test_save_architectural_design_generates_id(gc: GemstoneClient) -> None:
    design = ArchitecturalDesign(
        id="", device_id="h2-test", name="New", brightness=255,
        static_colors=[], is_favorite=False,
    )
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/deviceControl/architectural/save?deviceId=h2-test",
            payload={"data": {"id": "x", "deviceId": "h2-test", "name": "New"}},
        )
        await gc.save_architectural_design(design)
    _, put = _req(m, "PUT")
    assert put.kwargs["json"]["id"] == design.id != ""


@pytest.mark.rest
async def test_save_and_delete_pattern(gc: GemstoneClient) -> None:
    pattern = Pattern(
        id="", name="Ski Hill", colors=[255, 16711680], animation="chase",
        brightness=200, speed=100, extra_parameters={"version": 0},
    )
    with aioresponses() as m:
        m.put(
            re.compile(rf"{re.escape(REST_API_BASE)}/folders/pattern/save\?.*"),
            payload={
                "data": {
                    "id": "fp1", "ownerId": "o", "folderId": "f1",
                    "isFavorite": True, "createdAt": 1700000000,
                    "lastUpdatedAt": 1700000000,
                    "patternData": {"id": "p", "name": "Ski Hill",
                                    "colors": [255, 16711680]},
                }
            },
        )
        m.delete(
            re.compile(rf"{re.escape(REST_API_BASE)}/folders/pattern/delete\?.*"),
            payload={"message": "Successful.", "statusCode": 200},
        )
        saved = await gc.save_pattern("f1", pattern, is_favorite=True)
        before = int(time.time())
        await gc.delete_pattern("f1", "p1")
    assert saved.folder_id == "f1"
    url, put = _req(m, "PUT")
    assert url.query["folderId"] == "f1"
    assert url.query["patternId"] == pattern.id != ""
    body = put.kwargs["json"]
    assert body["isFavorite"] is True
    assert body["patternData"]["extraParameters"] == {"version": 0}
    assert body["patternData"]["animation"] == "chase"
    url, _ = _req(m, "DELETE")
    assert url.query["patternId"] == "p1"
    delta = int(url.query["deleteAfter"]) - before
    assert 30 * 86400 - 5 <= delta <= 30 * 86400 + 5


@pytest.mark.rest
async def test_timer_create_enable_delete(gc: GemstoneClient) -> None:
    pattern = Pattern(id="p1", name="Warm", colors=[255], reference_pattern_id="ref")
    with aioresponses() as m:
        m.post(
            f"{REST_API_BASE}/timer/create?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-t"}},
        )
        m.put(
            f"{REST_API_BASE}/timer/enabled?id=t1&deviceOrGroupId=h2-test",
            payload={"statusCode": 200},
        )
        m.delete(
            f"{REST_API_BASE}/timer/delete?deviceOrGroupId=h2-test&id=t1",
            payload={"statusCode": 200},
        )
        timer = await gc.create_timer(
            "h2-test", "hg1", name="Evening", on_time="sunset",
            off_time="22:00", pattern=pattern, timer_id="t1",
        )
        await gc.set_timer_enabled("h2-test", "t1", False)
        await gc.delete_timer("h2-test", "t1")
    assert timer.id == "t1"
    assert timer.tx_id == "tx-t"
    assert timer.timer_data is not None and timer.timer_data.off_time == "22:00"
    assert timer.pattern is not None and timer.pattern.reference_pattern_id == "ref"
    _, post = _req(m, "POST")
    t = post.kwargs["json"]["timer"]
    assert t["timerData"] == {"onTime": "sunset", "offTime": "22:00", "timerType": "daily"}
    assert t["assigneeId"] == "h2-test" and t["homegroupId"] == "hg1"
    assert t["timerPatternData"]["pattern"]["referencePatternId"] == "ref"
    _, put = _req(m, "PUT")
    assert put.kwargs["json"] == {"enabled": False}


@pytest.mark.rest
async def test_timer_create_weekly_and_yearly(gc: GemstoneClient) -> None:
    pattern = Pattern(id="p1", name="Warm", colors=[255], background_color=0)
    with aioresponses() as m:
        url = f"{REST_API_BASE}/timer/create?deviceOrGroupId=h2-test"
        m.post(url, payload={"data": {"txId": "tx-w"}})
        m.post(url, payload={"data": {"txId": "tx-y"}})
        weekly = await gc.create_timer(
            "h2-test", "hg1", name="MWF", on_time="sunset", off_time="23:00",
            pattern=pattern, timer_type="weekly", days_of_week=[5, 1, 3, 3],
            on_offset_minutes=-45,
        )
        yearly = await gc.create_timer(
            "h2-test", "hg1", name="Xmas", on_time="sunset", off_time="23:00",
            pattern=pattern, timer_type="yearly",
            start_date="12-25", end_date="12-25",
        )
    calls = [c for (meth, _), cs in m.requests.items() if meth == "POST" for c in cs]
    w, y = (c.kwargs["json"]["timer"] for c in calls)
    assert w["timerData"] == {
        "onTime": "sunset", "offTime": "23:00", "timerType": "weekly",
        "onOffsetInMinutes": -45, "repeatDaysOfTheWeek": [1, 3, 5],
    }
    assert y["timerData"] == {
        "onTime": "sunset", "offTime": "23:00", "timerType": "yearly",
        "startDate": "12-25", "endDate": "12-25",
        "repeatDaysOfTheWeek": [0, 1, 2, 3, 4, 5, 6],
    }
    assert w["timerPatternData"]["pattern"]["backgroundColor"] == 0
    assert weekly.timer_data is not None and weekly.timer_data.days_of_week == [1, 3, 5]
    assert yearly.timer_data is not None and yearly.timer_data.start_date == "12-25"


_LIST_URL = f"{REST_API_BASE}/timer/listByHomegroup?homegroupId=hg1"


def _listed(
    timer_id: str = "t1", *, name: str = "Evening", enabled: bool = True,
    timer_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"data": [{
        "id": timer_id, "name": name, "homegroupId": "hg1",
        "assigneeId": "h2-test", "enabled": enabled,
        "timerData": timer_data
        or {"timerType": "daily", "onTime": "sunset", "offTime": "22:00"},
        "timerPatternData": {"pattern": {"id": "p1", "name": "Warm", "colors": [255]}},
    }]}


def _calls(m: aioresponses) -> list[tuple[str, str]]:
    """Every request made, as (METHOD, path)."""
    return [
        (meth, url.path)
        for (meth, url), cs in m.requests.items() for _ in cs
    ]


@pytest.mark.rest
async def test_timer_update_puts_full_body(gc: GemstoneClient) -> None:
    pattern = Pattern(id="p1", name="Warm", colors=[255])
    with aioresponses() as m:
        m.post(
            f"{REST_API_BASE}/timer/create?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-c"}},
        )
        m.put(
            f"{REST_API_BASE}/timer/update?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-u"}},
        )
        timer = await gc.create_timer(
            "h2-test", "hg1", name="Evening", on_time="sunset",
            off_time="22:00", pattern=pattern, timer_id="t1",
        )
        assert timer.timer_data is not None
        timer.name = "Late"
        timer.timer_data.timer_type = "weekly"
        timer.timer_data.days_of_week = [6, 0]
        updated = await gc.update_timer(timer)
    _, put = _req(m, "PUT")
    t = put.kwargs["json"]["timer"]
    assert t["id"] == "t1" and t["name"] == "Late" and t["enabled"] is True
    assert t["assigneeId"] == "h2-test" and t["homegroupId"] == "hg1"
    assert t["timerData"]["repeatDaysOfTheWeek"] == [0, 6]
    assert updated.tx_id == "tx-u"
    assert not any(meth == "GET" for meth, _ in _calls(m))


@pytest.mark.rest
async def test_timer_create_disabled_waits_then_disables(
    gc: GemstoneClient,
) -> None:
    """The cloud ignores ``enabled`` on create; disable once it lands."""
    gc.timer_poll_interval = 0
    pattern = Pattern(id="p1", name="Warm", colors=[255])
    with aioresponses() as m:
        m.post(
            f"{REST_API_BASE}/timer/create?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-c"}},
        )
        m.get(_LIST_URL, payload={"data": []})
        m.get(_LIST_URL, payload=_listed(enabled=True))
        m.put(
            f"{REST_API_BASE}/timer/enabled?id=t1&deviceOrGroupId=h2-test",
            payload={"statusCode": 200},
        )
        m.get(_LIST_URL, payload=_listed(enabled=True))
        m.get(_LIST_URL, payload=_listed(enabled=False))
        timer = await gc.create_timer(
            "h2-test", "hg1", name="Evening", on_time="sunset",
            off_time="22:00", pattern=pattern, timer_id="t1", enabled=False,
        )
    assert timer.enabled is False
    gets = sum(1 for meth, _ in _calls(m) if meth == "GET")
    assert gets == 4
    _, put = _req(m, "PUT")
    assert put.kwargs["json"] == {"enabled": False}


@pytest.mark.rest
async def test_timer_update_disabled_waits_for_new_data_then_disables(
    gc: GemstoneClient,
) -> None:
    """Updates re-enable the timer; wait for the new data, then disable."""
    gc.timer_poll_interval = 0
    old = Timer.from_api(_listed(name="Evening", enabled=False)["data"][0])
    old.name = "Late"
    new_data = {"timerType": "daily", "onTime": "sunset", "offTime": "22:00"}
    with aioresponses() as m:
        m.put(
            f"{REST_API_BASE}/timer/update?deviceOrGroupId=h2-test",
            payload={"data": {"txId": "tx-u"}},
        )
        m.get(_LIST_URL, payload=_listed(name="Evening", enabled=False))
        m.get(_LIST_URL, payload=_listed(name="Late", timer_data=new_data))
        m.put(
            f"{REST_API_BASE}/timer/enabled?id=t1&deviceOrGroupId=h2-test",
            payload={"statusCode": 200},
        )
        m.get(_LIST_URL, payload=_listed(name="Late", enabled=False))
        await gc.update_timer(old)
    assert [meth for meth, _ in _calls(m)].count("GET") == 3
    enabled_puts = [
        c for (meth, url), cs in m.requests.items()
        if meth == "PUT" and url.path.endswith("/timer/enabled") for c in cs
    ]
    assert [c.kwargs["json"] for c in enabled_puts] == [{"enabled": False}]


@pytest.mark.rest
async def test_wait_for_timer_gone_and_timeout(gc: GemstoneClient) -> None:
    gc.timer_poll_interval = 0
    with aioresponses() as m:
        m.get(_LIST_URL, payload=_listed())
        m.get(_LIST_URL, payload={"data": []})
        assert await gc.wait_for_timer("hg1", "t1", present=False) is None
        m.get(_LIST_URL, payload={"data": []}, repeat=True)
        with pytest.raises(GemstoneTimeoutError):
            await gc.wait_for_timer("hg1", "t1", timeout=0)


@pytest.mark.rest
@pytest.mark.parametrize(
    "kwargs",
    [
        {"timer_type": "weekly"},
        {"timer_type": "weekly", "days_of_week": []},
        {"timer_type": "weekly", "days_of_week": [7]},
        {"timer_type": "yearly", "start_date": "12-25"},
        {"timer_type": "yearly", "start_date": "12-25", "end_date": "2026-12-25"},
        {"timer_type": "yearly", "start_date": "02-30", "end_date": "03-01"},
        {"timer_type": "monthly"},
    ],
)
async def test_timer_invalid_schedule_rejected_before_request(
    gc: GemstoneClient, kwargs: dict[str, Any]
) -> None:
    pattern = Pattern(id="p1", name="Warm", colors=[255])
    with aioresponses() as m, pytest.raises(ValueError):
        await gc.create_timer(
            "h2-test", "hg1", name="x", on_time="sunset", off_time="23:00",
            pattern=pattern, **kwargs,
        )
    assert not m.requests


@pytest.mark.rest
async def test_subscribed_events_past(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.get(
            f"{REST_API_BASE}/events/listSubscribedPast?homegroupId=hg1",
            payload={"data": []},
        )
        assert await gc.subscribed_events_past("hg1") == []
