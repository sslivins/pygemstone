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
from .models import DeviceState, HomeGroup, Pattern

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
    "GemstoneError",
    "GemstoneAuthError",
    "GemstoneApiError",
    "GemstoneConnectionError",
    "GemstoneNotFoundError",
    "GemstoneValueError",
    "__version__",
]
