"""Typed dataclasses for the Gemstone API response surface.

These mirror the JSON shapes returned by the cloud, with a small
amount of normalisation (timestamps → ``datetime``, colours kept as
raw packed ints since they're convenient to push back unchanged).

Colours use Gemstone's little-endian, red-in-the-low-byte layout
(``0xWWBBGGRR``) — see :mod:`pygemstone.color` for ``unpack_color`` /
``pack_color`` / ``color_to_hex`` helpers rather than decoding the
ints by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

TIMER_TYPES = ("daily", "weekly", "yearly")
_MM_DD = re.compile(r"\d{2}-\d{2}")


def encode_lights(indices: Any) -> list[int]:
    """Encode 0-based light indices into Gemstone's compressed ``lights`` list.

    The wire format is a flat list where a lone value is one light and a
    repeated value ``a, a, b`` is the inclusive range ``a..b``. Like the
    official app, runs of four or more consecutive lights are compressed
    and shorter runs are sent as individual indices (``[0, 1, 2]`` but
    ``[0, 0, 3]``). Input order and duplicates are ignored.
    """
    ordered = sorted({int(i) for i in indices})
    if any(i < 0 for i in ordered):
        raise ValueError("light indices must be >= 0")
    out: list[int] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        if j - i + 1 >= 4:
            out.extend([ordered[i], ordered[i], ordered[j]])
        else:
            out.extend(ordered[i : j + 1])
        i = j + 1
    return out


def decode_lights(encoded: Any) -> list[int]:
    """Expand a compressed Gemstone ``lights`` list into sorted 0-based indices.

    Inverse of :func:`encode_lights`: ``[0, 0, 3, 7]`` → ``[0, 1, 2, 3, 7]``.
    """
    values = [int(v) for v in encoded or []]
    result: set[int] = set()
    i = 0
    while i < len(values):
        if i + 2 < len(values) and values[i] == values[i + 1]:
            start, end = values[i], values[i + 2]
            if end < start:
                raise ValueError(f"invalid light range {start}..{end}")
            result.update(range(start, end + 1))
            i += 3
        else:
            result.add(values[i])
            i += 1
    return sorted(result)


def _ts(value: Any) -> datetime | None:
    """Convert a Gemstone unix-seconds timestamp to a tz-aware ``datetime``."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
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
    def from_api(cls, payload: dict[str, Any]) -> HomeGroup:
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
    def from_api(cls, payload: dict[str, Any]) -> Device:
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
    extra_parameters: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Pattern:
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
            extra_parameters=payload.get("extraParameters"),
            raw=payload,
        )

    def to_api(self) -> dict[str, Any]:
        """Render back to the wire format expected by ``play/pattern``."""
        if self.raw:
            return self.raw
        body: dict[str, Any] = {
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
        if self.extra_parameters is not None:
            body["extraParameters"] = self.extra_parameters
        return body


@dataclass(slots=True)
class DeviceState:
    """Current playback state of a device, as reported by ``currentlyPlaying``."""

    device_id: str
    on_state: bool
    pattern: Pattern | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> DeviceState:
        pat = payload.get("pattern")
        return cls(
            device_id=payload["id"],
            on_state=bool(payload.get("onState", False)),
            pattern=Pattern.from_api(pat) if pat else None,
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class AccountProfile:
    """The signed-in user's account profile (``/account/profile``)."""

    id: str
    username: str
    email: str
    email_opt_in: bool = False
    cancelled_deletion: bool = False
    scanned_device_ids: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> AccountProfile:
        return cls(
            id=payload.get("id", ""),
            username=payload.get("username", ""),
            email=payload.get("email", ""),
            email_opt_in=bool(payload.get("emailOptIn", False)),
            cancelled_deletion=bool(payload.get("cancelledDeletion", False)),
            scanned_device_ids=dict(payload.get("scannedDeviceIds", {}) or {}),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class HomeGroupUser:
    """A member of a home group (``/homegroup/users``)."""

    user_id: str
    homegroup_id: str
    homegroup_name: str
    role: str
    invitation_status: str
    username: str
    email: str
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> HomeGroupUser:
        return cls(
            user_id=payload.get("userId", ""),
            homegroup_id=payload.get("homegroupId", ""),
            homegroup_name=payload.get("homegroupName", ""),
            role=payload.get("role", ""),
            invitation_status=payload.get("invitationStatus", ""),
            username=payload.get("username", ""),
            email=payload.get("email", ""),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class Folder:
    """A user-defined folder of patterns (``/folders/list``).

    ``gemstone_managed`` distinguishes Gemstone's curated folders
    (which can't be edited) from user-created ones.
    """

    folder_id: str
    name: str
    icon: str
    owner_id: str
    gemstone_managed: bool = False
    reference_folder_id: str | None = None
    background_color: int | None = None
    hidden: bool = False
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Folder:
        bg = payload.get("backgroundColor")
        return cls(
            folder_id=payload.get("folderId", ""),
            name=payload.get("name", ""),
            icon=payload.get("icon", ""),
            owner_id=payload.get("ownerId", ""),
            gemstone_managed=bool(payload.get("gemstoneManaged", False)),
            reference_folder_id=payload.get("referenceFolderId"),
            background_color=int(bg) if bg is not None else None,
            hidden=bool(payload.get("hidden", False)),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class FolderPattern:
    """A pattern slot inside a folder (``/folders/pattern/list``).

    The actual pattern body lives in ``pattern``; the rest is folder
    metadata describing how the pattern is associated with the folder
    (favourite flag, hidden, reference link back to the source).
    """

    id: str
    folder_id: str
    owner_id: str
    pattern: Pattern
    reference_pattern_id: str | None = None
    reference_folder_id: str | None = None
    is_favorite: bool = False
    hidden: bool = False
    gemstone_managed: bool = False
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> FolderPattern:
        pat_data = payload.get("patternData", {}) or {}
        return cls(
            id=payload.get("id", ""),
            folder_id=payload.get("folderId", ""),
            owner_id=payload.get("ownerId", ""),
            pattern=Pattern.from_api(pat_data),
            reference_pattern_id=payload.get("referencePatternId"),
            reference_folder_id=payload.get("referenceFolderId"),
            is_favorite=bool(payload.get("isFavorite", False)),
            hidden=bool(payload.get("hidden", False)),
            gemstone_managed=bool(payload.get("gemstoneManaged", False)),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class StaticColorSegment:
    """One coloured light segment within an :class:`ArchitecturalDesign`.

    ``lights`` is the compressed wire list (see :func:`encode_lights`);
    use :meth:`from_indices` / :attr:`indices` to work with plain 0-based
    light numbers. ``color`` uses the packed ``0xWWBBGGRR`` layout.
    """

    lights: list[int] = field(default_factory=list)
    color: int = 0

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> StaticColorSegment:
        return cls(
            lights=list(payload.get("lights", []) or []),
            color=int(payload.get("color", 0)),
        )

    @classmethod
    def from_indices(cls, indices: Any, color: int) -> StaticColorSegment:
        return cls(lights=encode_lights(indices), color=int(color))

    @property
    def indices(self) -> list[int]:
        """The 0-based light indices this segment covers."""
        return decode_lights(self.lights)

    def to_api(self) -> dict[str, Any]:
        return {"lights": self.lights, "color": self.color}


@dataclass(slots=True)
class ArchitecturalDesign:
    """A saved "Quick Access" / "Custom Design" look for one device.

    Unlike folder patterns, these are stored per-device (``deviceId``)
    rather than per-homegroup, via ``/deviceControl/architectural/list``
    and ``/deviceControl/architectural/save``. ``save`` only persists the
    record — it does **not** push the look to the lights. Activating a
    design is a separate device command, ``/deviceControl/play/architectural``
    (see :meth:`to_play_api` and ``GemstoneClient.play_architectural_design``).
    """

    id: str
    device_id: str
    name: str
    brightness: int = 255
    static_colors: list[StaticColorSegment] = field(default_factory=list)
    is_favorite: bool = False
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> ArchitecturalDesign:
        return cls(
            id=payload.get("id", ""),
            device_id=payload.get("deviceId", ""),
            name=payload.get("name", ""),
            brightness=int(payload.get("brightness", 255)),
            static_colors=[
                StaticColorSegment.from_api(sc)
                for sc in payload.get("staticColors", []) or []
            ],
            is_favorite=bool(payload.get("isFavorite", False)),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )

    def to_api(self) -> dict[str, Any]:
        """Render back to the wire format expected by ``architectural/save``."""
        return {
            "id": self.id,
            "deviceId": self.device_id,
            "name": self.name,
            "brightness": self.brightness,
            "staticColors": [sc.to_api() for sc in self.static_colors],
            "isFavorite": self.is_favorite,
        }

    def to_play_api(self, *, preview: bool = False) -> dict[str, Any]:
        """Render the body expected by ``deviceControl/play/architectural``.

        This is the *activate* command shape captured from the iOS app.
        It differs from :meth:`to_api`: the ``deviceId`` moves to the query
        string, ``isFavorite`` is dropped, and a ``preview`` flag is added
        (the app sends ``true`` while live-dragging, ``false`` to commit).
        """
        return {
            "brightness": self.brightness,
            "id": self.id,
            "name": self.name,
            "preview": preview,
            "staticColors": [sc.to_api() for sc in self.static_colors],
        }


@dataclass(slots=True)
class Zone:
    """A named, reusable range of lights on one device.

    From ``/deviceControl/zone/list``; created/updated with
    ``/deviceControl/zone/save`` (same call, client-chosen ``id``).
    ``lights`` uses the compressed encoding (see :func:`encode_lights`).
    """

    id: str
    device_id: str
    name: str
    lights: list[int] = field(default_factory=list)
    icon: str = "house_3"
    confirmed: bool = False
    tx_id: str = ""
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Zone:
        return cls(
            id=payload.get("id", ""),
            device_id=payload.get("deviceId", ""),
            name=payload.get("name", ""),
            lights=list(payload.get("lights", []) or []),
            icon=payload.get("icon", "") or "",
            confirmed=bool(payload.get("confirmed", False)),
            tx_id=payload.get("txId", "") or "",
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )

    @property
    def indices(self) -> list[int]:
        """The 0-based light indices in this zone."""
        return decode_lights(self.lights)

    def to_api(self) -> dict[str, Any]:
        """Render the body expected by ``deviceControl/zone/save``."""
        return {
            "deviceId": self.device_id,
            "name": self.name,
            "id": self.id,
            "lights": self.lights,
            "icon": self.icon,
            "confirmed": self.confirmed,
        }


@dataclass(slots=True)
class DownloadableFolder:
    """A Gemstone-curated folder available for download.

    From ``/downloads/folders/listGemstoneManaged``.
    """

    id: str
    name: str
    folder_name: str
    icon: str
    category: str
    uploader_id: str
    downloads: int = 0
    background_color: int | None = None
    badge: dict[str, Any] | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    approved_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> DownloadableFolder:
        bg = payload.get("backgroundColor")
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name", ""),
            folder_name=payload.get("folderName", ""),
            icon=payload.get("icon", ""),
            category=payload.get("category", ""),
            uploader_id=payload.get("uploaderId", ""),
            downloads=int(payload.get("downloads", 0) or 0),
            background_color=int(bg) if bg is not None else None,
            badge=payload.get("badge"),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            approved_at=_ts(payload.get("approvedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class DownloadablePattern:
    """A pattern available for download from the Gemstone catalogue.

    From ``/downloads/folders/pattern/listGemstoneManaged``.
    """

    id: str
    pattern: Pattern
    downloadable_folder_id: str
    category: str
    pattern_name: str
    uploader_id: str
    downloads: int = 0
    badge: dict[str, Any] | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    approved_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> DownloadablePattern:
        pat_data = payload.get("patternData", {}) or {}
        return cls(
            id=payload.get("id", ""),
            pattern=Pattern.from_api(pat_data),
            downloadable_folder_id=payload.get("downloadableFolderId", ""),
            category=payload.get("category", ""),
            pattern_name=payload.get("patternName", ""),
            uploader_id=payload.get("uploaderId", ""),
            downloads=int(payload.get("downloads", 0) or 0),
            badge=payload.get("badge"),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            approved_at=_ts(payload.get("approvedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class SwatchColor:
    """One named colour inside a :class:`Swatch`."""

    color: int
    name: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> SwatchColor:
        return cls(color=int(payload.get("color", 0)), name=payload.get("name", ""))


@dataclass(slots=True)
class Swatch:
    """A named colour palette (``/swatches/list``)."""

    id: str
    name: str
    owner_id: str
    colors: list[SwatchColor] = field(default_factory=list)
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Swatch:
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name", ""),
            owner_id=payload.get("ownerId", ""),
            colors=[
                SwatchColor.from_api(c)
                for c in payload.get("swatchesColorData", []) or []
            ],
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class EventsScheduleWindow:
    """Daily on/off window used by autopilot scheduling."""

    on_time: str
    off_time: str
    on_offset_minutes: int = 0
    off_offset_minutes: int = 0

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> EventsScheduleWindow:
        return cls(
            on_time=payload.get("onTime", ""),
            off_time=payload.get("offTime", ""),
            on_offset_minutes=int(payload.get("onOffsetInMinutes", 0) or 0),
            off_offset_minutes=int(payload.get("offOffsetInMinutes", 0) or 0),
        )

    def to_api(self) -> dict[str, Any]:
        return {
            "onTime": self.on_time,
            "offTime": self.off_time,
            "onOffsetInMinutes": int(self.on_offset_minutes),
            "offOffsetInMinutes": int(self.off_offset_minutes),
        }


@dataclass(slots=True)
class EventsSettings:
    """Home-group autopilot/scheduling settings (``/events/settings``)."""

    homegroup_id: str
    category_ids: list[str] = field(default_factory=list)
    device_ids: list[str] = field(default_factory=list)
    setup_yet: bool = False
    allow_static_patterns: bool = True
    allow_animated_patterns: bool = True
    schedule: EventsScheduleWindow | None = None
    # Autopilot brightness 0-255; ``None`` if the backend hasn't stored one.
    brightness: int | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_api(self) -> dict[str, Any]:
        """Full ``PUT /events/settings`` body.

        Starts from ``raw`` so keys this library doesn't model survive a
        read-modify-write; server-managed timestamps are dropped.
        """
        body = {
            k: v for k, v in self.raw.items()
            if k not in ("createdAt", "lastUpdatedAt")
        }
        body.update(
            {
                "homegroupId": self.homegroup_id,
                "categoryIds": list(self.category_ids),
                "deviceIds": list(self.device_ids),
                "setupYet": bool(self.setup_yet),
                "allowStaticPatterns": bool(self.allow_static_patterns),
                "allowAnimatedPatterns": bool(self.allow_animated_patterns),
            }
        )
        if self.schedule is not None:
            body["schedule"] = self.schedule.to_api()
        if self.brightness is not None:
            body["brightness"] = max(0, min(255, int(self.brightness)))
        return body

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> EventsSettings:
        sched = payload.get("schedule")
        bright = payload.get("brightness")
        return cls(
            homegroup_id=payload.get("homegroupId", ""),
            category_ids=list(payload.get("categoryIds", []) or []),
            device_ids=list(payload.get("deviceIds", []) or []),
            setup_yet=bool(payload.get("setupYet", False)),
            allow_static_patterns=bool(payload.get("allowStaticPatterns", True)),
            allow_animated_patterns=bool(payload.get("allowAnimatedPatterns", True)),
            schedule=EventsScheduleWindow.from_api(sched) if sched else None,
            brightness=int(bright) if bright is not None else None,
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class SubscribedEvent:
    """A scheduled autopilot event (``/events/listSubscribed``).

    Each subscribed event represents a date range (e.g. "Memorial Day")
    bound to a category, with a pool of static and animated patterns
    that can play on that day plus a current ``selected_pattern``.
    """

    event_id: str
    name: str
    homegroup_id: str
    category_id: str
    category_name: str
    icon: str
    group: str
    year_month_half: str
    start_date: str
    end_date: str
    background_color: int | None = None
    static_patterns: list[Pattern] = field(default_factory=list)
    animated_patterns: list[Pattern] = field(default_factory=list)
    selected_pattern: Pattern | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> SubscribedEvent:
        bg = payload.get("backgroundColor")
        sel = payload.get("selectedPattern")
        return cls(
            event_id=payload.get("eventId", ""),
            name=payload.get("name", ""),
            homegroup_id=payload.get("homegroupId", ""),
            category_id=payload.get("categoryId", ""),
            category_name=payload.get("categoryName", ""),
            icon=payload.get("icon", ""),
            group=payload.get("group", ""),
            year_month_half=payload.get("yearMonthHalf", ""),
            start_date=payload.get("startDate", ""),
            end_date=payload.get("endDate", ""),
            background_color=int(bg) if bg is not None else None,
            static_patterns=[
                Pattern.from_api(p) for p in payload.get("staticPatterns", []) or []
            ],
            animated_patterns=[
                Pattern.from_api(p) for p in payload.get("animatedPatterns", []) or []
            ],
            selected_pattern=Pattern.from_api(sel) if sel else None,
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class TimerData:
    """The schedule portion of a :class:`Timer` (``timerData``).

    ``timer_type`` is ``"daily"``, ``"weekly"`` or ``"yearly"``.
    ``days_of_week`` (``repeatDaysOfTheWeek``) uses 0 = Sunday .. 6 =
    Saturday and is required for weekly/yearly. Yearly timers also need
    ``start_date``/``end_date`` as ``"MM-DD"`` (inclusive; the same date
    for a single day). ``on_offset_minutes`` shifts a ``"sunset"`` /
    ``"sunrise"`` on-time (e.g. ``-45``).
    """

    timer_type: str
    on_time: str
    off_time: str
    days_of_week: list[int] | None = None
    start_date: str | None = None
    end_date: str | None = None
    on_offset_minutes: int | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> TimerData:
        days = payload.get("repeatDaysOfTheWeek")
        offset = payload.get("onOffsetInMinutes")
        return cls(
            timer_type=payload.get("timerType", ""),
            on_time=payload.get("onTime", ""),
            off_time=payload.get("offTime", ""),
            days_of_week=[int(d) for d in days] if days is not None else None,
            start_date=payload.get("startDate"),
            end_date=payload.get("endDate"),
            on_offset_minutes=int(offset) if offset is not None else None,
        )

    def validate(self) -> None:
        """Raise ``ValueError`` if the schedule can't be sent to the API."""
        if self.timer_type not in TIMER_TYPES:
            raise ValueError(f"timer_type must be one of {TIMER_TYPES}")
        if self.timer_type in ("weekly", "yearly"):
            if not self.days_of_week:
                raise ValueError(f"{self.timer_type} timers need days_of_week")
            if any(not 0 <= int(d) <= 6 for d in self.days_of_week):
                raise ValueError("days_of_week values must be 0 (Sun) .. 6 (Sat)")
        if self.timer_type == "yearly":
            for label, value in (("start_date", self.start_date), ("end_date", self.end_date)):
                if not value or not _MM_DD.fullmatch(value):
                    raise ValueError(f"yearly timers need {label} as 'MM-DD'")
                month, day = (int(p) for p in value.split("-"))
                try:
                    date(2024, month, day)  # leap year, so 02-29 is allowed
                except ValueError as exc:
                    raise ValueError(f"invalid {label} {value!r}") from exc

    def to_api(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "onTime": self.on_time,
            "offTime": self.off_time,
            "timerType": self.timer_type,
        }
        if self.on_offset_minutes is not None:
            out["onOffsetInMinutes"] = int(self.on_offset_minutes)
        if self.timer_type == "yearly":
            out["startDate"] = self.start_date
            out["endDate"] = self.end_date
        if self.timer_type in ("weekly", "yearly") and self.days_of_week is not None:
            out["repeatDaysOfTheWeek"] = sorted({int(d) for d in self.days_of_week})
        return out


@dataclass(slots=True)
class Timer:
    """A scheduled on/off timer for a device or device group.

    From ``/timer/listByHomegroup``. Each timer binds a recurring
    on/off window (``timer_data``) plus an optional pattern that
    should play when it turns on (``pattern``).
    """

    id: str
    name: str
    homegroup_id: str
    assignee_id: str
    enabled: bool
    timer_data: TimerData | None = None
    pattern: Pattern | None = None
    tx_id: str = ""
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Timer:
        td = payload.get("timerData")
        tpd = (payload.get("timerPatternData") or {}).get("pattern")
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name", ""),
            homegroup_id=payload.get("homegroupId", ""),
            assignee_id=payload.get("assigneeId", ""),
            enabled=bool(payload.get("enabled", False)),
            timer_data=TimerData.from_api(td) if td else None,
            pattern=Pattern.from_api(tpd) if tpd else None,
            tx_id=payload.get("txId", ""),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )


@dataclass(slots=True)
class EventCategory:
    """A holiday / event category that can power autopilot subscriptions.

    From ``/events/listCategories``. Categories are grouped (``general``,
    ``nhl``, etc.); team-level categories often lack ``icon`` and
    ``background_color``.
    """

    id: str
    name: str
    description: str
    group: str
    icon: str | None = None
    background_color: int | None = None
    suggested: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> EventCategory:
        bg = payload.get("backgroundColor")
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            group=payload.get("group", ""),
            icon=payload.get("icon"),
            background_color=int(bg) if bg is not None else None,
            suggested=bool(payload.get("suggested", False)),
            raw=payload,
        )


@dataclass(slots=True)
class Announcement:
    """An in-app announcement (``/announcements``)."""

    id: str
    title: str
    description_text: str
    icon: str
    start_date: str
    end_date: str
    roles: list[str] = field(default_factory=list)
    background_color: int | None = None
    minimum_app_version: str | None = None
    close_button_text: str = ""
    close_button_action: str = ""
    close_action_value: str = ""
    done_button_text: str = ""
    done_button_action: str = ""
    done_action_value: str = ""
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Announcement:
        bg = payload.get("backgroundColor")
        return cls(
            id=payload.get("id", ""),
            title=payload.get("title", ""),
            description_text=payload.get("descriptionText", ""),
            icon=payload.get("icon", ""),
            start_date=payload.get("startDate", ""),
            end_date=payload.get("endDate", ""),
            roles=list(payload.get("roles", []) or []),
            background_color=int(bg) if bg is not None else None,
            minimum_app_version=payload.get("minimumAppVersion"),
            close_button_text=payload.get("closeButtonText", ""),
            close_button_action=payload.get("closeButtonAction", ""),
            close_action_value=payload.get("closeActionValue", ""),
            done_button_text=payload.get("doneButtonText", ""),
            done_button_action=payload.get("doneButtonAction", ""),
            done_action_value=payload.get("doneActionValue", ""),
            created_at=_ts(payload.get("createdAt")),
            last_updated_at=_ts(payload.get("lastUpdatedAt")),
            raw=payload,
        )
