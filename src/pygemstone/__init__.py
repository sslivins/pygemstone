"""pygemstone — Python client for Gemstone Lights permanent Christmas lights."""

from .auth import GemstoneAuth, TokenSet
from .client import GemstoneClient
from .device import Device
from .errors import (
    GemstoneApiError,
    GemstoneAuthError,
    GemstoneConnectionError,
    GemstoneError,
    GemstoneNotFoundError,
    GemstoneValueError,
)
from .models import Device as DeviceRecord
from .models import (
    AccountProfile,
    Announcement,
    DeviceState,
    DownloadableFolder,
    DownloadablePattern,
    EventsScheduleWindow,
    EventsSettings,
    Folder,
    FolderPattern,
    HomeGroup,
    HomeGroupUser,
    Pattern,
    SubscribedEvent,
    Swatch,
    SwatchColor,
)

__version__ = "0.0.1"

__all__ = [
    "GemstoneClient",
    "GemstoneAuth",
    "TokenSet",
    "Device",
    "DeviceRecord",
    "DeviceState",
    "HomeGroup",
    "Pattern",
    "AccountProfile",
    "Announcement",
    "DownloadableFolder",
    "DownloadablePattern",
    "EventsScheduleWindow",
    "EventsSettings",
    "Folder",
    "FolderPattern",
    "HomeGroupUser",
    "SubscribedEvent",
    "Swatch",
    "SwatchColor",
    "GemstoneError",
    "GemstoneAuthError",
    "GemstoneApiError",
    "GemstoneConnectionError",
    "GemstoneNotFoundError",
    "GemstoneValueError",
    "__version__",
]
