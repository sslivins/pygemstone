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
    def from_api(cls, payload: dict[str, Any]) -> "AccountProfile":
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
    def from_api(cls, payload: dict[str, Any]) -> "HomeGroupUser":
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
    def from_api(cls, payload: dict[str, Any]) -> "Folder":
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
    def from_api(cls, payload: dict[str, Any]) -> "FolderPattern":
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
    def from_api(cls, payload: dict[str, Any]) -> "DownloadableFolder":
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
    def from_api(cls, payload: dict[str, Any]) -> "DownloadablePattern":
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
    def from_api(cls, payload: dict[str, Any]) -> "SwatchColor":
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
    def from_api(cls, payload: dict[str, Any]) -> "Swatch":
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
    def from_api(cls, payload: dict[str, Any]) -> "EventsScheduleWindow":
        return cls(
            on_time=payload.get("onTime", ""),
            off_time=payload.get("offTime", ""),
            on_offset_minutes=int(payload.get("onOffsetInMinutes", 0) or 0),
            off_offset_minutes=int(payload.get("offOffsetInMinutes", 0) or 0),
        )


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
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "EventsSettings":
        sched = payload.get("schedule")
        return cls(
            homegroup_id=payload.get("homegroupId", ""),
            category_ids=list(payload.get("categoryIds", []) or []),
            device_ids=list(payload.get("deviceIds", []) or []),
            setup_yet=bool(payload.get("setupYet", False)),
            allow_static_patterns=bool(payload.get("allowStaticPatterns", True)),
            allow_animated_patterns=bool(payload.get("allowAnimatedPatterns", True)),
            schedule=EventsScheduleWindow.from_api(sched) if sched else None,
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
    def from_api(cls, payload: dict[str, Any]) -> "SubscribedEvent":
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
    """The schedule portion of a :class:`Timer` (``timerData``)."""

    timer_type: str
    on_time: str
    off_time: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TimerData":
        return cls(
            timer_type=payload.get("timerType", ""),
            on_time=payload.get("onTime", ""),
            off_time=payload.get("offTime", ""),
        )


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
    def from_api(cls, payload: dict[str, Any]) -> "Timer":
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
    def from_api(cls, payload: dict[str, Any]) -> "EventCategory":
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
    def from_api(cls, payload: dict[str, Any]) -> "Announcement":
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
