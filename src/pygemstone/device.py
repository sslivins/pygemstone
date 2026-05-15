"""Device convenience wrapper.

A :class:`Device` ties a :class:`pygemstone.models.Device` record to
the :class:`pygemstone.client.GemstoneClient` that produced it, so
callers can write ``await device.turn_on()`` instead of plumbing the
client + id pair through every call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import Device as DeviceRecord, DeviceState, Pattern

if TYPE_CHECKING:
    from .client import GemstoneClient


class Device:
    """A Gemstone controller bound to a live client."""

    def __init__(self, client: "GemstoneClient", payload: dict[str, Any]) -> None:
        self._client = client
        self._record = DeviceRecord.from_api(payload)
        self._state: DeviceState | None = None

    @property
    def id(self) -> str:
        return self._record.id

    @property
    def name(self) -> str:
        return self._record.name

    @property
    def homegroup_id(self) -> str:
        return self._record.homegroup_id

    @property
    def firmware(self) -> str | None:
        return self._record.firmware

    @property
    def record(self) -> DeviceRecord:
        return self._record

    @property
    def state(self) -> DeviceState | None:
        """Last state returned by :meth:`refresh`, or ``None`` if not fetched yet."""
        return self._state

    async def refresh(self) -> DeviceState:
        self._state = await self._client.device_state(self.id)
        return self._state

    async def turn_on(self) -> str:
        return await self._client.set_on_state(self.id, True)

    async def turn_off(self) -> str:
        return await self._client.set_on_state(self.id, False)

    async def play_pattern(self, pattern: Pattern) -> str:
        return await self._client.play_pattern(self.id, pattern)

    def __repr__(self) -> str:
        return f"<Device id={self.id!r} name={self.name!r}>"
