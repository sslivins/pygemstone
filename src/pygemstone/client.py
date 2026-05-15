"""High-level Gemstone Lights client.

Wraps :class:`pygemstone.auth.GemstoneAuth` with an ``aiohttp`` session
and exposes typed methods over the REST API uncovered in the iOS app
capture (:mod:`pygemstone.const`).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, AsyncIterator, Self

import aiohttp

from .auth import GemstoneAuth
from .const import DEFAULT_TIMEOUT, REST_API_BASE, USER_AGENT
from .device import Device
from .errors import (
    GemstoneApiError,
    GemstoneAuthError,
    GemstoneConnectionError,
)
from .models import (
    AccountProfile,
    Announcement,
    DeviceState,
    DownloadableFolder,
    DownloadablePattern,
    EventsSettings,
    Folder,
    FolderPattern,
    HomeGroup,
    HomeGroupUser,
    Pattern,
    SubscribedEvent,
    Swatch,
)

logger = logging.getLogger(__name__)


class GemstoneClient:
    """Async client for the Gemstone Lights AWS Amplify backend.

    Use as an async context manager so the underlying
    :class:`aiohttp.ClientSession` is cleaned up::

        async with GemstoneClient("you@example.com", "secret") as gc:
            await gc.login()
            devices = await gc.devices()
            await devices[0].turn_on()
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        api_base: str = REST_API_BASE,
    ) -> None:
        self._auth = GemstoneAuth(email, password)
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._api_base = api_base.rstrip("/")
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def auth(self) -> GemstoneAuth:
        return self._auth

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError(
                "GemstoneClient must be used as an async context manager "
                "or constructed with an explicit aiohttp.ClientSession."
            )
        return self._session

    async def login(self) -> None:
        await self._auth.login()

    async def logout(self) -> None:
        await self._auth.logout()

    async def homegroups(self) -> list[HomeGroup]:
        payload = await self._get("/homegroup/list")
        return [HomeGroup.from_api(g) for g in payload.get("data", [])]

    async def devices(self, homegroup_id: str | None = None) -> list[Device]:
        """List devices across one (or all) home groups.

        If ``homegroup_id`` is omitted, the first home group from
        :meth:`homegroups` is used. Users with multiple home groups
        should pass an explicit id.
        """
        if homegroup_id is None:
            groups = await self.homegroups()
            if not groups:
                return []
            homegroup_id = groups[0].id
        payload = await self._get(
            "/homegroup/devices", params={"homegroupId": homegroup_id}
        )
        return [Device(self, d) for d in payload.get("data", [])]

    async def device_state(self, device_or_group_id: str) -> DeviceState:
        payload = await self._get(
            "/deviceControl/currentlyPlaying",
            params={"deviceOrGroupId": device_or_group_id},
        )
        return DeviceState.from_api(payload["data"])

    async def set_on_state(self, device_or_group_id: str, on: bool) -> str:
        payload = await self._put(
            "/deviceControl/onState",
            params={"deviceOrGroupId": device_or_group_id},
            json_body={"onState": bool(on)},
        )
        return str(payload.get("data", {}).get("txId", ""))

    async def play_pattern(
        self, device_or_group_id: str, pattern: Pattern
    ) -> str:
        payload = await self._put(
            "/deviceControl/play/pattern",
            params={"deviceOrGroupId": device_or_group_id},
            json_body={"pattern": pattern.to_api()},
        )
        return str(payload.get("data", {}).get("txId", ""))

    # ------------------------------------------------------------------
    # Account / home-group admin
    # ------------------------------------------------------------------

    async def account_profile(self) -> AccountProfile:
        """Return the signed-in user's profile."""
        payload = await self._get("/account/profile")
        return AccountProfile.from_api(payload.get("data", {}) or {})

    async def homegroup_users(self, homegroup_id: str) -> list[HomeGroupUser]:
        """List the members of a home group."""
        payload = await self._get(
            "/homegroup/users", params={"homegroupId": homegroup_id}
        )
        return [HomeGroupUser.from_api(u) for u in payload.get("data", []) or []]

    async def invitations(
        self, status: str = "pending"
    ) -> list[dict[str, Any]]:
        """List home-group invitations for the signed-in user.

        The capture only saw an empty list for ``status="pending"`` so we
        don't yet know the per-invitation schema; raw dicts are returned
        unchanged.
        """
        payload = await self._get(
            "/homegroup/invitation", params={"invitationStatus": status}
        )
        return list(payload.get("data", []) or [])

    async def device_groups(self, homegroup_id: str) -> list[dict[str, Any]]:
        """List device groups (multi-device zones) in a home group.

        The capture saw an empty list — the per-group schema is not yet
        known — so raw dicts are returned.
        """
        payload = await self._get(
            "/deviceGroup/list", params={"homegroupId": homegroup_id}
        )
        return list(payload.get("data", []) or [])

    # ------------------------------------------------------------------
    # Pattern catalogue
    # ------------------------------------------------------------------

    async def folders(self) -> list[Folder]:
        """List the user's own pattern folders."""
        payload = await self._get("/folders/list")
        return [Folder.from_api(f) for f in payload.get("data", []) or []]

    async def folder_patterns(self, page: int = 1) -> list[FolderPattern]:
        """One page of the user's saved patterns across all folders."""
        payload = await self._get(
            "/folders/pattern/list", params={"page": str(page)}
        )
        return [FolderPattern.from_api(p) for p in payload.get("data", []) or []]

    async def save_folder(
        self, folder_id: str, body: dict[str, Any]
    ) -> Folder:
        """Create or update a folder.

        ``body`` should match the wire shape sent by the official app
        (``folderId``, ``ownerId``, ``name``, ``icon``,
        ``backgroundColor``, ``isSynchronized``, ``createdAt``,
        ``newFolder``).
        """
        payload = await self._put(
            "/folders/save", params={"folderId": folder_id}, json_body=body
        )
        return Folder.from_api(payload.get("data", {}) or {})

    async def swatches(self) -> list[Swatch]:
        """List the user's colour swatches (named palettes)."""
        payload = await self._get("/swatches/list")
        return [Swatch.from_api(s) for s in payload.get("data", []) or []]

    async def downloadable_folders(
        self, page: int = 1
    ) -> list[DownloadableFolder]:
        """One page of Gemstone-curated downloadable folders."""
        payload = await self._get(
            "/downloads/folders/listGemstoneManaged", params={"page": str(page)}
        )
        return [
            DownloadableFolder.from_api(f) for f in payload.get("data", []) or []
        ]

    async def downloadable_patterns(
        self, page: int = 1
    ) -> list[DownloadablePattern]:
        """One page of Gemstone-curated downloadable patterns."""
        payload = await self._get(
            "/downloads/folders/pattern/listGemstoneManaged",
            params={"page": str(page)},
        )
        return [
            DownloadablePattern.from_api(p) for p in payload.get("data", []) or []
        ]

    # ------------------------------------------------------------------
    # Autopilot / scheduling
    # ------------------------------------------------------------------

    async def events_settings(self, homegroup_id: str) -> EventsSettings:
        """Autopilot calendar + daily schedule for a home group."""
        payload = await self._get(
            "/events/settings", params={"homegroupId": homegroup_id}
        )
        return EventsSettings.from_api(payload.get("data", {}) or {})

    async def subscribed_events(
        self, homegroup_id: str, page: int = 0
    ) -> list[SubscribedEvent]:
        """One page of subscribed autopilot events (e.g. holidays)."""
        payload = await self._get(
            "/events/listSubscribed",
            params={"homegroupId": homegroup_id, "page": str(page)},
        )
        return [SubscribedEvent.from_api(e) for e in payload.get("data", []) or []]

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    async def announcements(self) -> list[Announcement]:
        """In-app announcements (welcome messages, promotions, etc.)."""
        payload = await self._get("/announcements")
        return [Announcement.from_api(a) for a in payload.get("data", []) or []]

    @asynccontextmanager
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        url = f"{self._api_base}{path}"
        headers = await self._auth.bearer_headers()
        headers["User-Agent"] = USER_AGENT
        headers["Accept"] = "application/json"
        try:
            async with self.session.request(
                method, url, params=params, json=json_body, headers=headers
            ) as resp:
                yield resp
        except aiohttp.ClientError as exc:
            raise GemstoneConnectionError(f"{method} {path} failed: {exc}") from exc

    async def _get(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        async with self._request("GET", path, params=params) as resp:
            return await self._handle(resp)

    async def _put(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> dict[str, Any]:
        async with self._request(
            "PUT", path, params=params, json_body=json_body
        ) as resp:
            return await self._handle(resp)

    async def _post(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> dict[str, Any]:
        async with self._request(
            "POST", path, params=params, json_body=json_body
        ) as resp:
            return await self._handle(resp)

    @staticmethod
    async def _handle(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        text = await resp.text()
        if resp.status in (401, 403):
            raise GemstoneAuthError(
                f"Auth rejected: HTTP {resp.status}: {text[:512]}"
            )
        if resp.status >= 400:
            raise GemstoneApiError(resp.status, text)
        if not text:
            return {}
        try:
            data: dict[str, Any] = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            raise GemstoneApiError(
                resp.status, text, message=f"Invalid JSON: {exc}"
            ) from exc
        return data
