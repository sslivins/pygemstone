# pygemstone

Standalone Python library for **Gemstone Lights** permanent-Christmas-light
controllers.

Gemstone's mobile app talks to an AWS Amplify backend
([Cognito](https://aws.amazon.com/cognito/) +
[API Gateway](https://aws.amazon.com/api-gateway/) +
[AppSync](https://aws.amazon.com/appsync/)) in `us-west-2`, so this library
is essentially:

- a Cognito SRP login wrapper (delegated to
  [`pycognito`](https://pypi.org/project/pycognito/))
- an aiohttp REST client for the public endpoints that control the
  lights (`/deviceControl/onState`, `/deviceControl/play/pattern`, etc.)

> **Status:** alpha — under active reverse-engineering of the iOS
> `com.gemstone.lights` app. APIs will change.

## Features

- Async login / token refresh (via Cognito User Pool SRP)
- List home groups and devices
- Read current state (on/off, active pattern, brightness)
- Turn lights on / off
- Replay or push a pattern

## Planned

- AppSync real-time subscriptions for live state push
- Device-group control (we have the endpoint, just not the schema yet)
- Schedules and event subscriptions
- Pattern catalogue browsing

## Installation

```
pip install pygemstone
```

## Usage

```python
import asyncio
from pygemstone import GemstoneClient

async def main():
    async with GemstoneClient("you@example.com", "...") as gc:
        await gc.login()
        for group in await gc.homegroups():
            print(group.name)
            for device in await gc.devices(group.id):
                state = await device.refresh()
                print(" ", device.name, "on" if state.on_state else "off")
                if not state.on_state:
                    await device.turn_on()

asyncio.run(main())
```

## CLI

A small CLI is provided for manual testing:

```
python -m pygemstone login
python -m pygemstone list
python -m pygemstone state <DEVICE_ID>
python -m pygemstone on <DEVICE_ID>
python -m pygemstone off <DEVICE_ID>
```

Credentials are read from `GEMSTONE_EMAIL` / `GEMSTONE_PASSWORD` env
vars, or a `.env` file in the working directory.

## Security note

Like the other Amplify-based IoT services, Gemstone's Cognito user pool
id and app client id are public values that any decompiled IPA / packet
capture exposes — they're shipped in [`const.py`](src/pygemstone/const.py)
as defaults. Do **not** commit credential files, JWT tokens, or
mitmproxy `.flows` files.

## Reverse-engineering notes

The endpoint catalogue was derived from a `mitmproxy --mode wireguard`
capture of the official iOS app. Notes are kept private (the capture
contains a live Cognito session); the public endpoint shape is in
[`const.py`](src/pygemstone/const.py).

## License

MIT — see [`LICENSE`](LICENSE).
