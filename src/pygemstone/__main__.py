"""Tiny CLI for manual smoke-testing pygemstone.

Usage:

    python -m pygemstone login        # verify credentials work
    python -m pygemstone list         # list home groups + devices
    python -m pygemstone state <DSN>  # print currentlyPlaying for a device
    python -m pygemstone on <DSN>     # turn a device on
    python -m pygemstone off <DSN>    # turn a device off

Credentials come from ``$GEMSTONE_EMAIL`` and ``$GEMSTONE_PASSWORD``
or, if absent, a ``.env`` file in the current directory.
"""

from __future__ import annotations

import asyncio
import os
import sys

from .client import GemstoneClient


def _load_env() -> tuple[str, str]:
    email = os.environ.get("GEMSTONE_EMAIL")
    password = os.environ.get("GEMSTONE_PASSWORD")
    if not (email and password):
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        email = os.environ.get("GEMSTONE_EMAIL")
        password = os.environ.get("GEMSTONE_PASSWORD")
    if not (email and password):
        print(
            "Missing GEMSTONE_EMAIL / GEMSTONE_PASSWORD in environment.",
            file=sys.stderr,
        )
        sys.exit(2)
    return email, password


async def _run(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    email, password = _load_env()
    async with GemstoneClient(email, password) as gc:
        await gc.login()
        if cmd == "login":
            tokens = gc.auth.tokens
            assert tokens is not None
            print(f"OK, access token expires at {tokens.expires_at:.0f}")
            return 0
        if cmd == "list":
            for group in await gc.homegroups():
                print(f"[{group.id}] {group.name} (role={group.role})")
                for dev in await gc.devices(group.id):
                    print(f"    {dev.id}  {dev.name}  fw={dev.firmware}")
            return 0
        if cmd == "state" and rest:
            state = await gc.device_state(rest[0])
            pat = state.pattern
            print(
                f"on={state.on_state}  "
                f"pattern={(pat.name if pat else None)!r}  "
                f"updated={state.last_updated_at}"
            )
            return 0
        if cmd in ("on", "off") and rest:
            tx = await gc.set_on_state(rest[0], cmd == "on")
            print(f"OK tx={tx}")
            return 0
    print(__doc__, file=sys.stderr)
    return 2


def main() -> None:  # pragma: no cover - entry point
    sys.exit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":  # pragma: no cover
    main()
