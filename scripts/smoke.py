"""Ad-hoc live smoke test against the real Gemstone backend.

Reads GEMSTONE_EMAIL / GEMSTONE_PASSWORD from .env (or env vars) and
exercises every read-only REST method shipped in the library. Does
NOT toggle any device state.

Usage::

    cd C:\\Users\\stesli\\code\\pygemstone
    .venv\\Scripts\\python.exe scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from typing import Any, Awaitable

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from pygemstone import GemstoneClient


def banner(label: str) -> None:
    print(f"\n=== {label} ===")


async def main() -> int:
    email = os.environ.get("GEMSTONE_EMAIL")
    password = os.environ.get("GEMSTONE_PASSWORD")
    if not email or not password:
        print("Missing GEMSTONE_EMAIL / GEMSTONE_PASSWORD")
        return 2

    fails: list[str] = []

    async def step(label: str, coro: Awaitable[Any]) -> Any:
        try:
            return await coro
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{label}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=3)
            return None

    async with GemstoneClient(email, password) as gc:
        banner("login")
        await step("login", gc.login())
        print("  logged in")

        banner("account_profile")
        profile = await step("account_profile", gc.account_profile())
        if profile:
            print(f"  user={profile.username!r}  email={profile.email!r}")

        banner("homegroups")
        groups = await step("homegroups", gc.homegroups()) or []
        for g in groups:
            print(f"  {g.id}  {g.name!r}  role={g.role}")

        if not groups:
            print("  (no home groups - stopping)")
            return 0
        hg = groups[0]

        banner("homegroup_users")
        users = await step("homegroup_users", gc.homegroup_users(hg.id)) or []
        for u in users:
            print(f"  {u.user_id}  {u.username!r}  role={u.role}")

        banner("invitations")
        invs = await step("invitations", gc.invitations()) or []
        print(f"  {len(invs)} pending invitation(s)")

        banner("device_groups")
        dgs = await step("device_groups", gc.device_groups(hg.id)) or []
        print(f"  {len(dgs)} device group(s)")

        banner("devices")
        devices = await step("devices", gc.devices(hg.id)) or []
        for d in devices:
            print(f"  {d.id}  {d.name!r}  fw={d.firmware}")

        banner("device_state")
        for d in devices:
            state = await step(f"device_state({d.id})", gc.device_state(d.id))
            if state:
                pat = state.pattern.name if state.pattern else "<no pattern>"
                print(f"  {d.id}  on={state.on_state}  pattern={pat!r}")

        banner("folders")
        folders = await step("folders", gc.folders()) or []
        print(f"  {len(folders)} folder(s)")
        for f in folders[:5]:
            print(f"    {f.folder_id}  {f.name!r}  managed={f.gemstone_managed}")

        banner("folder_patterns (page=1)")
        fps = await step("folder_patterns", gc.folder_patterns(page=1)) or []
        print(f"  {len(fps)} folder-pattern(s) on page 1")

        banner("swatches")
        swatches = await step("swatches", gc.swatches()) or []
        print(f"  {len(swatches)} swatch(es)")
        for s in swatches[:3]:
            print(f"    {s.id}  {s.name!r}  ({len(s.colors)} colours)")

        banner("downloadable_folders (page=1)")
        dfs = await step(
            "downloadable_folders", gc.downloadable_folders(page=1)
        ) or []
        print(f"  {len(dfs)} downloadable folder(s) on page 1")

        banner("downloadable_patterns (page=1)")
        dps = await step(
            "downloadable_patterns", gc.downloadable_patterns(page=1)
        ) or []
        print(f"  {len(dps)} downloadable pattern(s) on page 1")

        banner("events_settings")
        es = await step("events_settings", gc.events_settings(hg.id))
        if es:
            print(f"  setupYet={es.setup_yet}  categories={es.category_ids}")
            if es.schedule:
                print(f"  on={es.schedule.on_time}  off={es.schedule.off_time}")

        banner("subscribed_events (page=0)")
        evs = await step(
            "subscribed_events", gc.subscribed_events(hg.id, page=0)
        ) or []
        print(f"  {len(evs)} subscribed event(s) on page 0")
        for e in evs[:3]:
            print(f"    {e.event_id}  {e.name!r}  {e.start_date}..{e.end_date}")

        banner("events_categories (NEW)")
        cats = await step("events_categories", gc.events_categories()) or []
        print(f"  {len(cats)} category(ies)")
        by_group: dict[str, int] = {}
        for c in cats:
            by_group[c.group] = by_group.get(c.group, 0) + 1
        for g_name, n in sorted(by_group.items()):
            print(f"    {g_name}: {n}")

        banner("timers_by_homegroup (NEW)")
        timers = await step(
            "timers_by_homegroup", gc.timers_by_homegroup(hg.id)
        ) or []
        print(f"  {len(timers)} timer(s)")
        for t in timers:
            td = t.timer_data
            schedule = (
                f"{td.timer_type} {td.on_time}->{td.off_time}" if td else "?"
            )
            pat = t.pattern.name if t.pattern else "<no pattern>"
            print(
                f"    {t.id}  {t.name!r}  -> {t.assignee_id}  "
                f"{schedule}  pattern={pat!r}"
            )

        banner("announcements")
        anns = await step("announcements", gc.announcements()) or []
        print(f"  {len(anns)} announcement(s)")
        for a in anns[:3]:
            print(f"    {a.id}  {a.title!r}")

    print()
    if fails:
        print(f"FAIL: {len(fails)} call(s) raised:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("All calls succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
