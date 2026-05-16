"""AppSync GraphQL HTTP + real-time WebSocket transport.

.. warning::

    **Experimental — parked.** Two mitmproxy WireGuard captures of the
    official iOS app (``com.gemstone.lights`` 0.6.03, amplify-flutter
    2.6.5) show that the app **never opens a GraphQL connection** —
    even across logout/login, device control, and live state changes.
    All real-time state propagation observed in the wild happens via
    REST polling of ``/deviceControl/currentlyPlaying``. The only
    AppSync traffic seen is two unauthenticated ``GET /ping``
    healthchecks per session.

    Consequently the AppSync auth scheme used by the AppSync API
    (if any) is unknown. All four Cognito JWT auth modes
    (``Authorization: <id_token>``, ``Authorization: Bearer <id_token>``,
    and the same with the access token) return HTTP 401
    ``UnauthorizedException``. Cognito Identity Pool (AWS_IAM) is
    ruled out — no ``cognito-identity.us-west-2.amazonaws.com`` traffic
    was seen during a fresh login.

    This module is kept as scaffolding (transport, protocol, tests) so
    if Gemstone ever flips real-time on, we can finish wiring it once
    a successful subscription handshake is captured.

The Gemstone Lights cloud exposes an AWS AppSync GraphQL endpoint for
push-based state propagation. This module wraps both surfaces:

* :meth:`AppSyncClient.query` — POST GraphQL queries / mutations over
  HTTPS to the regular ``appsync-api`` host.
* :meth:`AppSyncClient.subscribe` — open a real-time subscription over
  the ``graphql-ws`` WebSocket protocol on the ``appsync-realtime-api``
  host and yield event payloads.

The WebSocket protocol implemented here is the one documented by AWS
for AppSync real-time subscriptions:

    1. Connect to ``wss://{realtime-host}/graphql?header=<b64>&payload=e30=``
       with ``Sec-WebSocket-Protocol: graphql-ws``.
    2. Send ``{"type":"connection_init"}``; expect ``connection_ack``.
    3. Send ``{"id":<uuid>,"type":"start","payload":{"data":<json>,
       "extensions":{"authorization":{...}}}}``; expect ``start_ack``.
    4. Receive ``{"type":"data","id":...,"payload":{"data":{...}}}``
       events; ``ka`` keepalives are ignored; ``complete`` ends the
       subscription.
    5. Send ``{"id":<uuid>,"type":"stop"}`` to unsubscribe.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import aiohttp

from .auth import GemstoneAuth
from .const import APPSYNC_API_URL, APPSYNC_REALTIME_URL, USER_AGENT
from .errors import GemstoneApiError, GemstoneConnectionError

logger = logging.getLogger(__name__)


_GRAPHQL_WS_PROTOCOL = "graphql-ws"

# Standard GraphQL introspection query. Trimmed to the parts we care
# about so the response is a couple of hundred KB at most; sufficient
# to recover every type, field, argument, and (crucially) subscription.
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          description
          type { ...TypeRef }
          defaultValue
        }
        type { ...TypeRef }
        isDeprecated
        deprecationReason
      }
      inputFields {
        name
        description
        type { ...TypeRef }
        defaultValue
      }
      interfaces { ...TypeRef }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes { ...TypeRef }
    }
  }
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType { kind name }
            }
          }
        }
      }
    }
  }
}
""".strip()


def _encode_auth_header(api_host: str, auth_token: str) -> str:
    """Base64-encode the JSON header object used in the WS query string."""
    obj = {"host": api_host, "Authorization": auth_token}
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _ws_connect_url(
    realtime_url: str, api_host: str, auth_token: str
) -> str:
    """Build the AppSync real-time WebSocket connect URL."""
    header_b64 = _encode_auth_header(api_host, auth_token)
    payload_b64 = base64.urlsafe_b64encode(b"{}").decode("ascii")
    sep = "&" if "?" in realtime_url else "?"
    return f"{realtime_url}{sep}header={header_b64}&payload={payload_b64}"


class AppSyncClient:
    """GraphQL client for Gemstone's AppSync endpoint.

    Reuses the host :class:`pygemstone.client.GemstoneClient`'s
    :class:`aiohttp.ClientSession` and shares its :class:`GemstoneAuth`
    so tokens refresh transparently.
    """

    def __init__(
        self,
        auth: GemstoneAuth,
        session: aiohttp.ClientSession,
        *,
        api_url: str = APPSYNC_API_URL,
        realtime_url: str = APPSYNC_REALTIME_URL,
    ) -> None:
        self._auth = auth
        self._session = session
        self._api_url = api_url
        self._realtime_url = realtime_url
        self._api_host = urlparse(api_url).netloc

    async def _auth_token(self) -> str:
        """The Cognito id_token used by AppSync user-pool auth.

        AppSync's ``AMAZON_COGNITO_USER_POOLS`` auth mode expects the
        Cognito **id token** (not access token) in the ``Authorization``
        header, with no ``Bearer`` prefix.
        """
        tokens = await self._auth.ensure_fresh()
        return tokens.id_token

    async def query(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        """Run a GraphQL query or mutation over HTTPS.

        Returns the ``data`` field of the GraphQL response. Raises
        :class:`GemstoneApiError` on HTTP errors or if the response
        contains a non-empty ``errors`` list.
        """
        token = await self._auth_token()
        body: dict[str, Any] = {"query": query}
        if variables is not None:
            body["variables"] = variables
        if operation_name is not None:
            body["operationName"] = operation_name
        headers = {
            "Authorization": token,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Host": self._api_host,
        }
        try:
            async with self._session.post(
                self._api_url, json=body, headers=headers
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise GemstoneApiError(resp.status, text)
                payload = json.loads(text) if text else {}
        except aiohttp.ClientError as exc:
            raise GemstoneConnectionError(f"AppSync POST failed: {exc}") from exc
        errors = payload.get("errors") or []
        if errors:
            raise GemstoneApiError(
                200, json.dumps(errors), message="GraphQL error"
            )
        data: dict[str, Any] = payload.get("data") or {}
        return data

    async def introspect(self) -> dict[str, Any]:
        """Dump the AppSync schema via the standard introspection query.

        Will return an empty dict (and log a warning) if the operator
        has disabled introspection on this AppSync API. In that case,
        the only way to discover subscription names is a fresh
        mitmproxy capture of the official app while a subscription is
        active.
        """
        try:
            return await self.query(INTROSPECTION_QUERY)
        except GemstoneApiError as exc:
            logger.warning("AppSync introspection failed: %s", exc)
            return {}

    @asynccontextmanager
    async def subscribe(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
        handshake_timeout: float = 15.0,
    ) -> AsyncIterator[AsyncIterator[dict[str, Any]]]:
        """Open a real-time subscription, yielding an async iterator of events.

        Usage::

            sub = "subscription OnUpdate($id: ID!) { onUpdate(id: $id) { ... } }"
            async with gc.appsync.subscribe(sub, variables={"id": dev}) as events:
                async for event in events:
                    print(event)  # GraphQL `data` field of each push

        The iterator ends cleanly when the server sends ``complete``;
        :class:`GemstoneApiError` is raised on protocol errors.
        """
        token = await self._auth_token()
        url = _ws_connect_url(self._realtime_url, self._api_host, token)
        sub_id = str(uuid.uuid4())
        try:
            async with self._session.ws_connect(
                url, protocols=(_GRAPHQL_WS_PROTOCOL,)
            ) as ws:
                await _ws_handshake(ws, handshake_timeout)
                await _ws_start(
                    ws,
                    sub_id,
                    query,
                    variables,
                    operation_name,
                    self._api_host,
                    token,
                    handshake_timeout,
                )
                try:
                    yield _ws_iterate(ws, sub_id)
                finally:
                    if not ws.closed:
                        try:
                            await ws.send_json({"id": sub_id, "type": "stop"})
                        except Exception:  # noqa: BLE001 - best-effort cleanup
                            pass
        except aiohttp.ClientError as exc:
            raise GemstoneConnectionError(
                f"AppSync WS connect failed: {exc}"
            ) from exc


async def _ws_handshake(
    ws: aiohttp.ClientWebSocketResponse, timeout: float
) -> None:
    await ws.send_json({"type": "connection_init"})
    msg = await ws.receive_json(timeout=timeout)
    if msg.get("type") != "connection_ack":
        raise GemstoneApiError(
            0,
            json.dumps(msg),
            message=f"unexpected AppSync handshake reply: {msg.get('type')}",
        )


async def _ws_start(
    ws: aiohttp.ClientWebSocketResponse,
    sub_id: str,
    query: str,
    variables: dict[str, Any] | None,
    operation_name: str | None,
    api_host: str,
    token: str,
    timeout: float,
) -> None:
    inner: dict[str, Any] = {"query": query}
    if variables is not None:
        inner["variables"] = variables
    if operation_name is not None:
        inner["operationName"] = operation_name
    await ws.send_json(
        {
            "id": sub_id,
            "type": "start",
            "payload": {
                "data": json.dumps(inner, separators=(",", ":")),
                "extensions": {
                    "authorization": {
                        "host": api_host,
                        "Authorization": token,
                    }
                },
            },
        }
    )
    while True:
        msg = await ws.receive_json(timeout=timeout)
        kind = msg.get("type")
        if kind == "start_ack":
            return
        if kind == "error":
            raise GemstoneApiError(
                0, json.dumps(msg.get("payload")), message="AppSync start error"
            )
        if kind in ("ka", "connection_ack"):
            continue
        raise GemstoneApiError(
            0, json.dumps(msg), message=f"unexpected start reply: {kind}"
        )


async def _ws_iterate(
    ws: aiohttp.ClientWebSocketResponse, sub_id: str
) -> AsyncIterator[dict[str, Any]]:
    async for msg in ws:
        if msg.type != aiohttp.WSMsgType.TEXT:
            continue
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            continue
        kind = data.get("type")
        if kind == "ka":
            continue
        if data.get("id") and data["id"] != sub_id:
            # Ignore traffic for any other subscription multiplexed on
            # the same WS (we don't currently open multiple, but be
            # safe).
            continue
        if kind == "complete":
            return
        if kind == "error":
            raise GemstoneApiError(
                0,
                json.dumps(data.get("payload")),
                message="AppSync subscription error",
            )
        if kind == "data":
            yield (data.get("payload") or {}).get("data") or {}
