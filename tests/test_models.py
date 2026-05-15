"""Model round-trip tests using sanitised samples from the iOS-app capture."""

from __future__ import annotations

import pytest

from pygemstone.models import Device, DeviceState, HomeGroup, Pattern


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
