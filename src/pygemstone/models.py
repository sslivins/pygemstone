"""Typed dataclasses for the Gemstone API response surface.

These mirror the JSON shapes returned by the cloud, with a small
amount of normalisation (timestamps → ``datetime``, ARGB ints → kept
as raw ints since they're convenient to push back unchanged).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _ts(value: Any) -> datetime | None:
    """Convert a Gemstone unix-seconds timestamp to a tz-aware ``datetime``."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class HomeGroup:
    """A user's "home group" — the top-level container for devices."""

    id: str
    name: str
    role: str
    scanned_device_ids: dict[str, str] = field(default_factory=dict)
    homegroup_user_ids: list[str] = field(default_factory=list)
    created_at: datetime | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "HomeGroup":
        return cls(
            id=payload["id"],
            name=payload.get("name", ""),
            role=payload.get("role", ""),
            scanned_device_ids=dict(payload.get("scannedDeviceIds", {}) or {}),
            homegroup_user_ids=list(payload.get("homegroupUserIds", []) or []),
            created_at=_ts(payload.get("createdAt")),
        )


@dataclass(slots=True)
class Device:
    """A physical Gemstone controller (one zone of lights)."""

    id: str
    name: str
    homegroup_id: str
    firmware: str | None = None
    disconnect_reason: str | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Device":
        return cls(
            id=payload["id"],
            name=payload.get("name", ""),
            homegroup_id=payload.get("homegroupId", ""),
            firmware=payload.get("firmware"),
            disconnect_reason=payload.get("disconnectReason"),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class Pattern:
    """A lighting pattern that can be played on a device.

    The cloud stores patterns as colour/animation tuples; we keep the
    full raw payload so callers can echo it back unchanged when
    replaying a pattern they previously read.
    """

    id: str
    name: str
    colors: list[int] = field(default_factory=list)
    animation: str = "motionless"
    brightness: int = 255
    speed: int = 128
    direction: int = 0
    background_color: int = 0
    reference_pattern_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Pattern":
        return cls(
            id=payload["id"],
            name=payload.get("name", ""),
            colors=list(payload.get("colors", []) or []),
            animation=payload.get("animation", "motionless"),
            brightness=int(payload.get("brightness", 255)),
            speed=int(payload.get("speed", 128)),
            direction=int(payload.get("direction", 0)),
            background_color=int(payload.get("backgroundColor", 0)),
            reference_pattern_id=payload.get("referencePatternId"),
            raw=payload,
        )

    def to_api(self) -> dict[str, Any]:
        """Render back to the wire format expected by ``play/pattern``."""
        if self.raw:
            return self.raw
        return {
            "id": self.id,
            "name": self.name,
            "colors": self.colors,
            "animation": self.animation,
            "brightness": self.brightness,
            "speed": self.speed,
            "direction": self.direction,
            "backgroundColor": self.background_color,
            "referencePatternId": self.reference_pattern_id,
        }


@dataclass(slots=True)
class DeviceState:
    """Current playback state of a device, as reported by ``currentlyPlaying``."""

    device_id: str
    on_state: bool
    pattern: Pattern | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "DeviceState":
        pat = payload.get("pattern")
        return cls(
            device_id=payload["id"],
            on_state=bool(payload.get("onState", False)),
            pattern=Pattern.from_api(pat) if pat else None,
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )
