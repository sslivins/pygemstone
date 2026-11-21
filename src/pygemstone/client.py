"""High-level Gemstone Lights client.

Wraps :class:`pygemstone.auth.GemstoneAuth` with an ``aiohttp`` session
and exposes typed methods over the REST API uncovered in the iOS app
capture (:mod:`pygemstone.const`).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any, Self

import aiohttp

from .appsync import AppSyncClient
from .auth import GemstoneAuth
from .const import DEFAULT_TIMEOUT, REST_API_BASE, USER_AGENT
from .device import Device
from .errors import (
    GemstoneApiError,
    GemstoneAuthError,
    GemstoneConnectionError,
    GemstoneTimeoutError,
)
from .models import (
    AccountProfile,
    Announcement,
    ArchitecturalDesign,
    DeviceState,
    DownloadableFolder,
    DownloadablePattern,
    EventCategory,
    EventsSettings,
    Folder,
    FolderPattern,
    HomeGroup,
    HomeGroupUser,
    Pattern,
    SubscribedEvent,
    Swatch,
    Timer,
    TimerData,
    Zone,
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
        self._appsync: AppSyncClient | None = None

    # Polling used by :meth:`wait_for_timer` (seconds).
    timer_poll_interval: float = 1.0
    timer_settle_timeout: float = 30.0

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

    @property
    def appsync(self) -> AppSyncClient:
        """Lazy :class:`AppSyncClient` sharing this client's auth + session."""
        if self._appsync is None:
            self._appsync = AppSyncClient(self._auth, self.session)
        return self._appsync

    async def graphql(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        """Run a GraphQL query / mutation against the AppSync endpoint."""
        return await self.appsync.query(
            query, variables=variables, operation_name=operation_name
        )

    async def introspect_schema(self) -> dict[str, Any]:
        """Dump the AppSync schema via standard GraphQL introspection."""
        return await self.appsync.introspect()

    def subscribe(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> Any:
        """Open a real-time AppSync subscription.

        Returns an async context manager yielding an async iterator of
        event payloads (see :meth:`AppSyncClient.subscribe`)::

            async with gc.subscribe("subscription { ... }") as events:
                async for event in events:
                    print(event)
        """
        return self.appsync.subscribe(
            query, variables=variables, operation_name=operation_name
        )

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

    async def save_pattern(
        self, folder_id: str, pattern: Pattern, *, is_favorite: bool = False
    ) -> FolderPattern:
        """Create or update a pattern in one of the user's folders.

        A blank ``pattern.id`` gets a new uuid. The saved pattern can then
        be played with :meth:`play_pattern`.
        """
        if not pattern.id:
            pattern.id = str(uuid.uuid4())
        data: dict[str, Any] = {
            "name": pattern.name,
            "colors": pattern.colors,
            "animation": pattern.animation,
            "brightness": pattern.brightness,
            "id": pattern.id,
            "speed": pattern.speed,
            "direction": pattern.direction,
            "backgroundColor": pattern.background_color,
        }
        if pattern.extra_parameters is not None:
            data["extraParameters"] = pattern.extra_parameters
        payload = await self._put(
            "/folders/pattern/save",
            params={"folderId": folder_id, "patternId": pattern.id},
            json_body={
                "isFavorite": bool(is_favorite),
                "gemstoneManaged": None,
                "hidden": None,
                "patternData": data,
            },
        )
        return FolderPattern.from_api(payload.get("data", {}) or {})

    async def delete_pattern(
        self, folder_id: str, pattern_id: str, *, retain_days: int = 30
    ) -> None:
        """Delete a pattern from a folder.

        The app soft-deletes with ``deleteAfter`` = now + 30 days.
        """
        await self._delete(
            "/folders/pattern/delete",
            params={
                "folderId": folder_id,
                "patternId": pattern_id,
                "deleteAfter": str(int(time.time()) + retain_days * 86400),
            },
        )

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
    # Architectural designs ("Custom Designs" / "Quick Access")
    # ------------------------------------------------------------------

    async def architectural_designs(self, device_id: str) -> list[ArchitecturalDesign]:
        """List a single device's saved "Custom Designs" (Quick Access).

        Unlike folder patterns these are per-device, not per-homegroup —
        discovered via a live capture since they're not returned by
        ``/folders/list`` or ``/folders/pattern/list``.
        """
        payload = await self._get(
            "/deviceControl/architectural/list", params={"deviceId": device_id}
        )
        return [
            ArchitecturalDesign.from_api(d) for d in payload.get("data", []) or []
        ]

    async def save_architectural_design(
        self, design: ArchitecturalDesign
    ) -> ArchitecturalDesign:
        """Create or update a device's custom design record.

        Pass a design with a blank ``id`` to create a new one, or an
        existing ``id`` to update it in place. This only persists the
        record — it does **not** apply the look to the lights. Use
        :meth:`play_architectural_design` to activate a design.
        """
        if not design.id:
            # The cloud expects a client-generated uuid (as the iOS app sends).
            design.id = str(uuid.uuid4())
        payload = await self._put(
            "/deviceControl/architectural/save",
            params={"deviceId": design.device_id},
            json_body=design.to_api(),
        )
        return ArchitecturalDesign.from_api(payload.get("data", {}) or {})

    async def delete_architectural_design(
        self, device_id: str, design_id: str
    ) -> None:
        """Delete a device's saved custom design."""
        await self._delete(
            "/deviceControl/architectural/delete",
            params={"deviceId": device_id, "architecturalId": design_id},
        )

    async def preview_architectural_design(
        self, design: ArchitecturalDesign
    ) -> str:
        """Show an unsaved design on the lights (the app's live-edit preview)."""
        body = design.to_play_api(preview=True)
        body["name"] = "Preview"
        payload = await self._put(
            "/deviceControl/play/architectural",
            params={"deviceId": design.device_id},
            json_body={"architectural": body},
        )
        return str(payload.get("data", {}).get("txId", ""))

    async def play_architectural_design(
        self, design: ArchitecturalDesign
    ) -> str:
        """Activate a custom design on the device's lights.

        Sends the ``/deviceControl/play/architectural`` command captured
        from the iOS app (``save`` alone does not change the lights).
        Returns the command's transaction id.
        """
        payload = await self._put(
            "/deviceControl/play/architectural",
            params={"deviceId": design.device_id},
            json_body={"architectural": design.to_play_api()},
        )
        return str(payload.get("data", {}).get("txId", ""))

    # ------------------------------------------------------------------
    # Zones (named light ranges) + light identification
    # ------------------------------------------------------------------

    async def zones(self, device_id: str) -> list[Zone]:
        """List a device's saved zones."""
        payload = await self._get(
            "/deviceControl/zone/list", params={"deviceId": device_id}
        )
        return [Zone.from_api(z) for z in payload.get("data", []) or []]

    async def save_zone(self, zone: Zone) -> Zone:
        """Create or update a zone (a blank ``id`` gets a new uuid)."""
        if not zone.id:
            zone.id = str(uuid.uuid4())
        payload = await self._put(
            "/deviceControl/zone/save",
            params={"deviceId": zone.device_id},
            json_body=zone.to_api(),
        )
        return Zone.from_api(payload.get("data", {}) or {})

    async def delete_zone(self, device_id: str, zone_id: str) -> None:
        """Delete a zone."""
        await self._delete(
            "/deviceControl/zone/delete",
            params={"deviceId": device_id, "zoneId": zone_id},
        )

    async def impulse(
        self,
        device_or_group_id: str,
        lights: list[int],
        *,
        color: int = 0,
        length_seconds: int = 0,
        blink_period_ms: int = 0,
    ) -> str:
        """Flash specific lights to identify them (used while drawing zones).

        ``lights`` is the compressed wire list (see ``encode_lights``).
        The app sends zeros for colour/length/period.
        """
        payload = await self._put(
            "/deviceControl/play/impulse",
            params={"deviceOrGroupId": device_or_group_id},
            json_body={
                "impulse": {
                    "lengthInSeconds": int(length_seconds),
                    "blinkPeriodMs": int(blink_period_ms),
                    "lights": list(lights),
                    "color": int(color),
                }
            },
        )
        return str(payload.get("data", {}).get("txId", ""))

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

    async def subscribed_events_past(
        self, homegroup_id: str
    ) -> list[SubscribedEvent]:
        """Subscribed autopilot events that have already happened."""
        payload = await self._get(
            "/events/listSubscribedPast", params={"homegroupId": homegroup_id}
        )
        return [SubscribedEvent.from_api(e) for e in payload.get("data", []) or []]

    async def events_categories(self) -> list[EventCategory]:
        """Full catalogue of autopilot event categories.

        Categories are grouped (``general``, ``nhl``, etc.) and feed the
        category picker in ``events_settings``.
        """
        payload = await self._get("/events/listCategories")
        return [EventCategory.from_api(c) for c in payload.get("data", []) or []]

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    async def timers_by_homegroup(self, homegroup_id: str) -> list[Timer]:
        """List the home group's scheduled on/off timers."""
        payload = await self._get(
            "/timer/listByHomegroup", params={"homegroupId": homegroup_id}
        )
        return [Timer.from_api(t) for t in payload.get("data", []) or []]

    @staticmethod
    def _timer_body(
        device_or_group_id: str,
        homegroup_id: str,
        timer_id: str,
        name: str,
        timer_data: TimerData,
        pattern: Pattern,
        enabled: bool,
    ) -> dict[str, Any]:
        timer_data.validate()
        return {
            "enabled": bool(enabled),
            "name": name,
            "timerData": timer_data.to_api(),
            "assigneeId": device_or_group_id,
            "homegroupId": homegroup_id,
            "timerPatternData": {
                "pattern": {
                    "name": pattern.name,
                    "colors": pattern.colors,
                    "animation": pattern.animation,
                    "brightness": pattern.brightness,
                    "id": pattern.id,
                    "speed": pattern.speed,
                    "direction": pattern.direction,
                    "referencePatternId": pattern.reference_pattern_id,
                    "backgroundColor": pattern.background_color,
                }
            },
            "id": timer_id,
        }

    async def create_timer(
        self,
        device_or_group_id: str,
        homegroup_id: str,
        *,
        name: str,
        on_time: str,
        off_time: str,
        pattern: Pattern,
        enabled: bool = True,
        timer_type: str = "daily",
        days_of_week: list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        on_offset_minutes: int | None = None,
        timer_id: str | None = None,
    ) -> Timer:
        """Create a timer that plays ``pattern`` between two times.

        ``on_time`` / ``off_time`` are ``"HH:MM"`` (24h) or ``"sunset"``
        / ``"sunrise"``. ``timer_type`` is ``"daily"``, ``"weekly"``
        (needs ``days_of_week``, 0 = Sunday) or ``"yearly"`` (also needs
        ``start_date`` / ``end_date`` as ``"MM-DD"``; use the same date
        for a single day). Yearly timers default to every weekday.
        """
        if timer_type == "yearly" and days_of_week is None:
            days_of_week = list(range(7))
        timer_data = TimerData(
            timer_type=timer_type,
            on_time=on_time,
            off_time=off_time,
            days_of_week=days_of_week,
            start_date=start_date,
            end_date=end_date,
            on_offset_minutes=on_offset_minutes,
        )
        body = self._timer_body(
            device_or_group_id, homegroup_id, timer_id or str(uuid.uuid4()),
            name, timer_data, pattern, enabled,
        )
        payload = await self._post(
            "/timer/create",
            params={"deviceOrGroupId": device_or_group_id},
            json_body={"timer": body},
        )
        body["txId"] = str((payload.get("data") or {}).get("txId", ""))
        timer = Timer.from_api(body)
        if not enabled:
            await self.wait_for_timer(homegroup_id, timer.id)
            await self._disable_timer(timer)
        return timer

    async def update_timer(self, timer: Timer) -> Timer:
        """Replace an existing timer (name, schedule, pattern, enabled).

        Edit a :class:`Timer` from :meth:`timers_by_homegroup` (or
        :meth:`create_timer`) and pass it back; ``timer_data`` and
        ``pattern`` are required.

        The cloud re-enables a timer on every update, so when
        ``timer.enabled`` is false this waits for the update to land
        and then disables it again.
        """
        if timer.timer_data is None or timer.pattern is None:
            raise ValueError("update_timer needs timer_data and pattern")
        body = self._timer_body(
            timer.assignee_id, timer.homegroup_id, timer.id, timer.name,
            timer.timer_data, timer.pattern, timer.enabled,
        )
        payload = await self._put(
            "/timer/update",
            params={"deviceOrGroupId": timer.assignee_id},
            json_body={"timer": body},
        )
        body["txId"] = str((payload.get("data") or {}).get("txId", ""))
        updated = Timer.from_api(body)
        if not timer.enabled:
            sent = (updated.name, body["timerData"])
            await self.wait_for_timer(
                timer.homegroup_id, timer.id,
                lambda t: t.timer_data is not None
                and (t.name, t.timer_data.to_api()) == sent,
            )
            await self._disable_timer(updated)
        return updated

    async def _disable_timer(self, timer: Timer) -> None:
        await self.set_timer_enabled(timer.assignee_id, timer.id, False)
        await self.wait_for_timer(
            timer.homegroup_id, timer.id, lambda t: not t.enabled
        )

    async def wait_for_timer(
        self,
        homegroup_id: str,
        timer_id: str,
        predicate: Callable[[Timer], bool] | None = None,
        *,
        present: bool = True,
        timeout: float | None = None,
    ) -> Timer | None:
        """Poll the timer list until a change has landed.

        Timer writes return before the device applies them, and a write
        sent while another is still pending for the same device is
        silently dropped. Wait on each write before sending the next.

        With ``present=True`` (default) returns the listed timer once it
        exists and ``predicate`` (if any) holds; with ``present=False``
        returns ``None`` once the timer is gone. Raises
        :class:`GemstoneTimeoutError` after ``timeout`` seconds
        (default :attr:`timer_settle_timeout`).
        """
        deadline = time.monotonic() + (
            self.timer_settle_timeout if timeout is None else timeout
        )
        while True:
            listed = {
                t.id: t for t in await self.timers_by_homegroup(homegroup_id)
            }
            found = listed.get(timer_id)
            if not present and found is None:
                return None
            if present and found is not None and (
                predicate is None or predicate(found)
            ):
                return found
            if time.monotonic() >= deadline:
                raise GemstoneTimeoutError(
                    f"timer {timer_id} did not settle in time"
                )
            await asyncio.sleep(self.timer_poll_interval)

    async def set_timer_enabled(
        self, device_or_group_id: str, timer_id: str, enabled: bool
    ) -> None:
        """Enable or disable a timer."""
        await self._put(
            "/timer/enabled",
            params={"id": timer_id, "deviceOrGroupId": device_or_group_id},
            json_body={"enabled": bool(enabled)},
        )

    async def delete_timer(self, device_or_group_id: str, timer_id: str) -> None:
        """Delete a timer."""
        await self._delete(
            "/timer/delete",
            params={"deviceOrGroupId": device_or_group_id, "id": timer_id},
        )

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

    async def _delete(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        async with self._request("DELETE", path, params=params) as resp:
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
        except Exception as exc:
            raise GemstoneApiError(
                resp.status, text, message=f"Invalid JSON: {exc}"
            ) from exc
        return data
