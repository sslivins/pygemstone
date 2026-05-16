"""Model round-trip tests using sanitised samples from the iOS-app capture."""

from __future__ import annotations

import pytest

from pygemstone.models import (
    AccountProfile,
    Announcement,
    Device,
    DeviceState,
    DownloadableFolder,
    DownloadablePattern,
    EventCategory,
    EventsSettings,
    Folder,
    FolderPattern,
    HomeGroup,
    HomeGroupUser,
    Pattern,
    SubscribedEvent,
    Swatch,
    Timer,
)


# Sample taken from GET /prod/homegroup/list, sensitive IDs scrubbed.
HOMEGROUP_SAMPLE = {
    "role": "homegroupOwner",
    "createdAt": 1734173119,
    "scannedDeviceIds": {"1767392003": "h2-1065-6kys"},
    "name": "Test Homegroup",
    "homegroupUserIds": ["00000000-0000-0000-0000-000000000001"],
    "id": "5bf619c5-7d30-45a3-abb5-000000000000",
}

# Sample taken from GET /prod/homegroup/devices.
DEVICE_SAMPLE = {
    "homegroupId": "5bf619c5-7d30-45a3-abb5-000000000000",
    "deviceGroups": {},
    "id": "h2-1065-6kys",
    "timerIds": [],
    "disconnectReason": None,
    "name": "Hot Tub",
    "firmware": "1.1.0",
    "lastUpdatedAt": 1778882067,
}

# Sample taken from GET /prod/deviceControl/currentlyPlaying.
STATE_SAMPLE = {
    "onState": False,
    "createdAt": 1778882067,
    "id": "h2-1065-6kys",
    "lastUpdatedAt": 1778882067,
    "pattern": {
        "backgroundColor": 0,
        "brightness": 255,
        "name": "2 on, 2 off BW",
        "id": "810a0993-ae3a-4711-a083-262162da7608",
        "colors": [4294967295, 4294967295, 0, 0],
        "animation": "motionless",
        "speed": 128,
        "direction": 0,
        "referencePatternId": "bd209c83-79c2-2f31-c3dc-3313dd0e59e0",
    },
}


# Sample taken from GET /prod/account/profile.
PROFILE_SAMPLE = {
    "username": "Tester",
    "scannedDeviceIds": {"1767392003": "h2-1065-6kys"},
    "id": "00000000-0000-0000-0000-000000000001",
    "lastUpdatedAt": 1734173108,
    "emailOptIn": False,
    "email": "tester@example.com",
    "createdAt": 1734173061,
    "cancelledDeletion": False,
}

# Sample taken from GET /prod/homegroup/users.
HOMEGROUP_USER_SAMPLE = {
    "userId": "00000000-0000-0000-0000-000000000001",
    "role": "homegroupOwner",
    "lastUpdatedAt": 1734173119,
    "createdAt": 1734173119,
    "invitationStatus": "approved",
    "homegroupName": "Test Homegroup",
    "homegroupId": "5bf619c5-7d30-45a3-abb5-000000000000",
    "username": "Tester",
    "email": "tester@example.com",
}

# Sample taken from GET /prod/folders/list.
FOLDER_SAMPLE = {
    "gemstoneManaged": False,
    "icon": "ice_hockey",
    "createdAt": 1753632068,
    "lastUpdatedAt": 1753632070,
    "backgroundColor": 4294960870,
    "name": "Vancouver Canucks",
    "ownerId": "00000000-0000-0000-0000-000000000001",
    "hidden": False,
    "referenceFolderId": "04015429-b1dd-a687-ed98-30b8ee56299e",
    "folderId": "549352c4-7507-4895-abad-a9a46e6af42b",
}

# Sample taken from GET /prod/folders/pattern/list.
FOLDER_PATTERN_SAMPLE = {
    "id": "5cbddc1d-aea9-4267-8280-188f1ebb15f3",
    "patternData": {
        "backgroundColor": 0,
        "brightness": 255,
        "name": "Pastel Hearts",
        "id": "5cbddc1d-aea9-4267-8280-188f1ebb15f3",
        "colors": [3437183, 16453106, 6190060, 15448029, 79934, 6553729],
        "speed": 224,
        "referencePatternId": "7b6e5fe8-947f-8027-962c-4e2358b1ff6d",
        "animation": "motionless",
        "direction": 0,
    },
    "gemstoneManaged": True,
    "referencePatternId": "7b6e5fe8-947f-8027-962c-4e2358b1ff6d",
    "folderId": "16a64251-5d3b-4540-9887-4392c920ceaa",
    "createdAt": 1768620004,
    "ownerId": "00000000-0000-0000-0000-000000000001",
    "referenceFolderId": "4678d595-8bbd-e8f6-8409-0f72e4cef4aa",
    "isFavorite": True,
    "lastUpdatedAt": 1768620004,
}

# Sample taken from GET /prod/swatches/list.
SWATCH_SAMPLE = {
    "createdAt": 1759866786,
    "lastUpdatedAt": 1759866786,
    "name": "Colors",
    "ownerId": "gemstoneLightsOwned",
    "swatchesColorData": [
        {"color": 4278190080, "name": "Warm White"},
        {"color": 16777215, "name": "Cool White"},
        {"color": 255, "name": "Red"},
    ],
    "id": "5d508896-72f6-f860-d14f-502de3de1900",
}

# Sample taken from GET /prod/events/settings.
EVENTS_SETTINGS_SAMPLE = {
    "categoryIds": ["fun", "special-events"],
    "schedule": {
        "onTime": "sunset",
        "offTime": "22:00",
        "onOffsetInMinutes": 0,
        "offOffsetInMinutes": 0,
    },
    "homegroupId": "5bf619c5-7d30-45a3-abb5-000000000000",
    "setupYet": True,
    "deviceIds": ["h2-1065-6kys"],
    "createdAt": 1767392199,
    "allowStaticPatterns": True,
    "lastUpdatedAt": 1767392199,
    "allowAnimatedPatterns": True,
}

# Sample taken from GET /prod/events/listSubscribed.
SUBSCRIBED_EVENT_SAMPLE = {
    "eventId": "2026-05-25-usa",
    "yearMonthHalf": "2026052",
    "endDate": "2026-05-25",
    "group": "general",
    "icon": "usa",
    "staticPatterns": [
        {
            "backgroundColor": 0,
            "brightness": 255,
            "name": "USA",
            "id": "fdebf462-2a4b-765b-f47e-c0add9a1b876",
            "colors": [255, 16711680, 4294967295],
            "speed": 128,
            "referencePatternId": "fdebf462-2a4b-765b-f47e-c0add9a1b876",
            "animation": "motionless",
            "direction": 0,
        }
    ],
    "backgroundColor": 4293126911,
    "categoryName": "USA",
    "createdAt": 1777324467,
    "startDate": "2026-05-25",
    "lastUpdatedAt": 1777324467,
    "name": "Memorial Day",
    "categoryId": "usa",
    "animatedPatterns": [],
    "homegroupId": "5bf619c5-7d30-45a3-abb5-000000000000",
    "selectedPattern": {
        "backgroundColor": 0,
        "brightness": 255,
        "name": "USA",
        "id": "fdebf462-2a4b-765b-f47e-c0add9a1b876",
        "colors": [255, 16711680, 4294967295],
        "speed": 128,
        "referencePatternId": "fdebf462-2a4b-765b-f47e-c0add9a1b876",
        "animation": "motionless",
        "direction": 0,
    },
}

# Sample taken from GET /prod/announcements.
ANNOUNCEMENT_SAMPLE = {
    "endDate": "2025-10-30",
    "icon": "house_with_garden",
    "doneActionValue": "https://www.gemstonelights.com/learn/zone-control-video/",
    "createdAt": 1759891921,
    "lastUpdatedAt": 1759891921,
    "doneButtonText": "Learn More",
    "closeActionValue": "Discover more on the Learn page.",
    "doneButtonAction": "learn",
    "closeButtonText": "Close",
    "roles": ["homegroupOwner", "homegroupManager", "homegroupMember"],
    "startDate": "2025-10-07",
    "descriptionText": "Play different patterns on different zones with Zone Control.",
    "id": "2025-10-07-to-10-30-zone-control",
    "backgroundColor": 4292734463,
    "closeButtonAction": "toast",
    "minimumAppVersion": "0.5.11",
    "title": "Introducing Zone Control",
}

# Sample taken from GET /prod/downloads/folders/listGemstoneManaged.
DOWNLOADABLE_FOLDER_SAMPLE = {
    "name": "Chinese New Year",
    "backgroundColor": 4292668927,
    "allCategoriesKey": "AllCategories",
    "badge": {"icon": "badge_check", "iconColor": 16747538, "title": "Official"},
    "id": "0979c8ed-43f3-cce3-eb08-06d103322ee1",
    "icon": "red_paper_lantern",
    "folderName": "Chinese New Year",
    "createdAt": 1716934884,
    "lastUpdatedAt": 1716934884,
    "category": "holidays",
    "downloads": 24,
    "folderNameLower": "chinese new year",
    "approvedAt": 1738787271,
    "uploaderId": "gemstoneLightsOwned",
}

# Sample taken from GET /prod/downloads/folders/pattern/listGemstoneManaged.
DOWNLOADABLE_PATTERN_SAMPLE = {
    "id": "1331a5ca-7f54-697b-44d1-b89a4be79a06",
    "createdAt": 1719571106,
    "uploaderId": "gemstoneLightsOwned",
    "downloads": 0,
    "lastUpdatedAt": 1719571106,
    "approvedAt": 1738787271,
    "category": "holidays",
    "patternData": {
        "backgroundColor": 0,
        "brightness": 255,
        "name": "1. Happy New Year",
        "id": "1331a5ca-7f54-697b-44d1-b89a4be79a06",
        "colors": [255, 87807],
        "speed": 128,
        "referencePatternId": "1331a5ca-7f54-697b-44d1-b89a4be79a06",
        "animation": "chase",
        "direction": 0,
    },
    "downloadableFolderId": "0979c8ed-43f3-cce3-eb08-06d103322ee1",
    "badge": {"icon": "badge_check", "iconColor": 16747538, "title": "Official"},
    "patternName": "1. Happy New Year",
}

# Sample taken from GET /prod/timer/listByHomegroup.
TIMER_SAMPLE = {
    "homegroupId": "5bf619c5-7d30-45a3-abb5-000000000000",
    "enabled": True,
    "lastUpdatedAt": 1777088648,
    "name": "AlphaTauri 2",
    "assigneeId": "h2-1065-6kys",
    "createdAt": 1767417846,
    "id": "38ec682f-e7c7-403e-87bc-ea4ec4003a46",
    "timerData": {"timerType": "daily", "onTime": "sunset", "offTime": "23:00"},
    "txId": "d6d6c9c2-4bb8-4203-b4f9-6d557f5166e6",
    "timerPatternData": {
        "pattern": {
            "backgroundColor": 0,
            "brightness": 255,
            "name": "Cinco de Mayo",
            "id": "2655d9b7-da0c-4f7e-95d9-8b96e55f643d",
            "referencePatternId": "40318d71-3d8c-97f4-d674-7d5b9ccb3b31",
            "speed": 128,
            "colors": [65280, 16777215, 255, 65280, 16777215, 255],
            "animation": "motionless",
            "direction": 0,
        }
    },
}

# Sample taken from GET /prod/events/listCategories.
EVENT_CATEGORY_GENERAL_SAMPLE = {
    "id": "christmas",
    "description": "Enjoy a new festive pattern every day from December 1 to 25.",
    "name": "Christmas",
    "group": "general",
    "icon": "christmas_tree",
    "backgroundColor": 4294115301,
    "suggested": True,
}

# A team-level category has no icon / backgroundColor.
EVENT_CATEGORY_NHL_SAMPLE = {
    "id": "anaheim-ducks",
    "description": "Anaheim Ducks in NHL",
    "name": "Anaheim Ducks",
    "group": "nhl",
}


@pytest.mark.unit
def test_homegroup_decode() -> None:
    g = HomeGroup.from_api(HOMEGROUP_SAMPLE)
    assert g.id == "5bf619c5-7d30-45a3-abb5-000000000000"
    assert g.name == "Test Homegroup"
    assert g.role == "homegroupOwner"
    assert g.scanned_device_ids == {"1767392003": "h2-1065-6kys"}
    assert g.created_at is not None
    assert g.created_at.year == 2024


@pytest.mark.unit
def test_device_decode() -> None:
    d = Device.from_api(DEVICE_SAMPLE)
    assert d.id == "h2-1065-6kys"
    assert d.name == "Hot Tub"
    assert d.firmware == "1.1.0"
    assert d.homegroup_id == "5bf619c5-7d30-45a3-abb5-000000000000"
    assert d.raw is DEVICE_SAMPLE


@pytest.mark.unit
def test_state_decode_with_pattern() -> None:
    s = DeviceState.from_api(STATE_SAMPLE)
    assert s.device_id == "h2-1065-6kys"
    assert s.on_state is False
    assert s.pattern is not None
    assert s.pattern.name == "2 on, 2 off BW"
    assert s.pattern.colors == [4294967295, 4294967295, 0, 0]
    assert s.pattern.animation == "motionless"
    assert s.pattern.brightness == 255


@pytest.mark.unit
def test_state_decode_without_pattern() -> None:
    payload = {**STATE_SAMPLE, "pattern": None}
    s = DeviceState.from_api(payload)
    assert s.pattern is None


@pytest.mark.unit
def test_pattern_round_trip() -> None:
    p = Pattern.from_api(STATE_SAMPLE["pattern"])
    # The raw payload is preserved verbatim, so to_api echoes it back
    # unchanged — important for replaying a pattern read from the API.
    assert p.to_api() is STATE_SAMPLE["pattern"]


@pytest.mark.unit
def test_pattern_to_api_from_constructed() -> None:
    p = Pattern(
        id="abc",
        name="Custom",
        colors=[255, 0, 0],
        animation="motionless",
        brightness=200,
        speed=128,
        direction=0,
        background_color=0,
        reference_pattern_id="ref",
    )
    payload = p.to_api()
    assert payload["name"] == "Custom"
    assert payload["colors"] == [255, 0, 0]
    assert payload["brightness"] == 200
    assert payload["backgroundColor"] == 0
    assert payload["referencePatternId"] == "ref"


@pytest.mark.unit
def test_account_profile_decode() -> None:
    p = AccountProfile.from_api(PROFILE_SAMPLE)
    assert p.id == "00000000-0000-0000-0000-000000000001"
    assert p.username == "Tester"
    assert p.email == "tester@example.com"
    assert p.email_opt_in is False
    assert p.cancelled_deletion is False
    assert p.scanned_device_ids == {"1767392003": "h2-1065-6kys"}


@pytest.mark.unit
def test_homegroup_user_decode() -> None:
    u = HomeGroupUser.from_api(HOMEGROUP_USER_SAMPLE)
    assert u.user_id == "00000000-0000-0000-0000-000000000001"
    assert u.role == "homegroupOwner"
    assert u.invitation_status == "approved"
    assert u.homegroup_name == "Test Homegroup"
    assert u.email == "tester@example.com"


@pytest.mark.unit
def test_folder_decode() -> None:
    f = Folder.from_api(FOLDER_SAMPLE)
    assert f.folder_id == "549352c4-7507-4895-abad-a9a46e6af42b"
    assert f.name == "Vancouver Canucks"
    assert f.icon == "ice_hockey"
    assert f.gemstone_managed is False
    assert f.background_color == 4294960870
    assert f.hidden is False


@pytest.mark.unit
def test_folder_pattern_decode() -> None:
    fp = FolderPattern.from_api(FOLDER_PATTERN_SAMPLE)
    assert fp.id == "5cbddc1d-aea9-4267-8280-188f1ebb15f3"
    assert fp.folder_id == "16a64251-5d3b-4540-9887-4392c920ceaa"
    assert fp.is_favorite is True
    assert fp.gemstone_managed is True
    assert fp.pattern.name == "Pastel Hearts"
    assert fp.pattern.speed == 224


@pytest.mark.unit
def test_swatch_decode() -> None:
    s = Swatch.from_api(SWATCH_SAMPLE)
    assert s.id == "5d508896-72f6-f860-d14f-502de3de1900"
    assert s.name == "Colors"
    assert len(s.colors) == 3
    assert s.colors[0].name == "Warm White"
    assert s.colors[0].color == 4278190080


@pytest.mark.unit
def test_events_settings_decode() -> None:
    es = EventsSettings.from_api(EVENTS_SETTINGS_SAMPLE)
    assert es.homegroup_id == "5bf619c5-7d30-45a3-abb5-000000000000"
    assert es.setup_yet is True
    assert "fun" in es.category_ids
    assert es.device_ids == ["h2-1065-6kys"]
    assert es.schedule is not None
    assert es.schedule.on_time == "sunset"
    assert es.schedule.off_time == "22:00"


@pytest.mark.unit
def test_subscribed_event_decode() -> None:
    ev = SubscribedEvent.from_api(SUBSCRIBED_EVENT_SAMPLE)
    assert ev.event_id == "2026-05-25-usa"
    assert ev.name == "Memorial Day"
    assert ev.category_id == "usa"
    assert ev.start_date == "2026-05-25"
    assert len(ev.static_patterns) == 1
    assert ev.static_patterns[0].name == "USA"
    assert ev.selected_pattern is not None
    assert ev.selected_pattern.id == "fdebf462-2a4b-765b-f47e-c0add9a1b876"


@pytest.mark.unit
def test_announcement_decode() -> None:
    a = Announcement.from_api(ANNOUNCEMENT_SAMPLE)
    assert a.id == "2025-10-07-to-10-30-zone-control"
    assert a.title == "Introducing Zone Control"
    assert a.icon == "house_with_garden"
    assert a.minimum_app_version == "0.5.11"
    assert "homegroupOwner" in a.roles


@pytest.mark.unit
def test_downloadable_folder_decode() -> None:
    df = DownloadableFolder.from_api(DOWNLOADABLE_FOLDER_SAMPLE)
    assert df.id == "0979c8ed-43f3-cce3-eb08-06d103322ee1"
    assert df.name == "Chinese New Year"
    assert df.category == "holidays"
    assert df.downloads == 24
    assert df.badge is not None
    assert df.badge["title"] == "Official"


@pytest.mark.unit
def test_downloadable_pattern_decode() -> None:
    dp = DownloadablePattern.from_api(DOWNLOADABLE_PATTERN_SAMPLE)
    assert dp.id == "1331a5ca-7f54-697b-44d1-b89a4be79a06"
    assert dp.pattern_name == "1. Happy New Year"
    assert dp.category == "holidays"
    assert dp.pattern.animation == "chase"
    assert dp.downloadable_folder_id == "0979c8ed-43f3-cce3-eb08-06d103322ee1"


@pytest.mark.unit
def test_timer_decode() -> None:
    t = Timer.from_api(TIMER_SAMPLE)
    assert t.id == "38ec682f-e7c7-403e-87bc-ea4ec4003a46"
    assert t.name == "AlphaTauri 2"
    assert t.assignee_id == "h2-1065-6kys"
    assert t.enabled is True
    assert t.timer_data is not None
    assert t.timer_data.timer_type == "daily"
    assert t.timer_data.on_time == "sunset"
    assert t.timer_data.off_time == "23:00"
    assert t.pattern is not None
    assert t.pattern.name == "Cinco de Mayo"
    assert t.tx_id == "d6d6c9c2-4bb8-4203-b4f9-6d557f5166e6"


@pytest.mark.unit
def test_timer_decode_without_pattern() -> None:
    payload = {**TIMER_SAMPLE, "timerPatternData": {}}
    t = Timer.from_api(payload)
    assert t.pattern is None
    assert t.timer_data is not None


@pytest.mark.unit
def test_event_category_general_decode() -> None:
    c = EventCategory.from_api(EVENT_CATEGORY_GENERAL_SAMPLE)
    assert c.id == "christmas"
    assert c.name == "Christmas"
    assert c.group == "general"
    assert c.icon == "christmas_tree"
    assert c.background_color == 4294115301
    assert c.suggested is True


@pytest.mark.unit
def test_event_category_team_decode() -> None:
    c = EventCategory.from_api(EVENT_CATEGORY_NHL_SAMPLE)
    assert c.id == "anaheim-ducks"
    assert c.group == "nhl"
    assert c.icon is None
    assert c.background_color is None
    assert c.suggested is False
