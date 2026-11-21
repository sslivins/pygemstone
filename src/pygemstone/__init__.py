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
    GemstoneTimeoutError,
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
    Zone,
    decode_lights,
    encode_lights,
)
from .models import Device as DeviceRecord

__version__ = "0.2.0"

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
    "GemstoneTimeoutError",
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
    "Zone",
    "__version__",
    "color_to_hex",
    "decode_lights",
    "encode_lights",
    "pack_color",
    "unpack_color",
]
