"""pygemstone — Python client for Gemstone Lights permanent Christmas lights."""

from .appsync import AppSyncClient
from .auth import GemstoneAuth, TokenSet
from .client import GemstoneClient
from .color import color_to_hex, pack_color, unpack_color
from .device import Device
from .errors import (
    GemstoneApiError,
    GemstoneAuthError,
    GemstoneConnectionError,
    GemstoneError,
    GemstoneNotFoundError,
    GemstoneValueError,
)
from .models import (
    AccountProfile,
    Announcement,
    ArchitecturalDesign,
    DeviceState,
    DownloadableFolder,
    DownloadablePattern,
    EventCategory,
    EventsScheduleWindow,
    EventsSettings,
    Folder,
    FolderPattern,
    HomeGroup,
    HomeGroupUser,
    Pattern,
    StaticColorSegment,
    SubscribedEvent,
    Swatch,
    SwatchColor,
    Timer,
    TimerData,
)
from .models import Device as DeviceRecord

__version__ = "0.0.1"

__all__ = [
    "AccountProfile",
    "Announcement",
    "AppSyncClient",
    "ArchitecturalDesign",
    "Device",
    "DeviceRecord",
    "DeviceState",
    "DownloadableFolder",
    "DownloadablePattern",
    "EventCategory",
    "EventsScheduleWindow",
    "EventsSettings",
    "Folder",
    "FolderPattern",
    "GemstoneApiError",
    "GemstoneAuth",
    "GemstoneAuthError",
    "GemstoneClient",
    "GemstoneConnectionError",
    "GemstoneError",
    "GemstoneNotFoundError",
    "GemstoneValueError",
    "HomeGroup",
    "HomeGroupUser",
    "Pattern",
    "StaticColorSegment",
    "SubscribedEvent",
    "Swatch",
    "SwatchColor",
    "Timer",
    "TimerData",
    "TokenSet",
    "__version__",
    "color_to_hex",
    "pack_color",
    "unpack_color",
]
