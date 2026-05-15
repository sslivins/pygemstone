"""Tests for the AppSync GraphQL HTTP + WS transport."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import aiohttp
import pytest
from aioresponses import aioresponses

from pygemstone.appsync import (
    INTROSPECTION_QUERY,
    _encode_auth_header,
    _ws_connect_url,
    _ws_handshake,
    _ws_iterate,
    _ws_start,
)
from pygemstone.auth import TokenSet
from pygemstone.client import GemstoneClient
from pygemstone.const import APPSYNC_API_URL
from pygemstone.errors import GemstoneApiError


# ---------------------------------------------------------------------------
# WS handshake helpers (pure unit tests)
# ---------------------------------------------------------------------------


class _FakeMsg:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.type = aiohttp.WSMsgType.TEXT
        self.data = json.dumps(payload)


class FakeWS:
    """A stand-in for :class:`aiohttp.ClientWebSocketResponse`.

    Supports both the ``send_json`` / ``receive_json`` surface (used
    during the handshake + start dance) and ``async for`` iteration
    (used by the subscription event loop). ``inbox`` is consumed in
    order across both APIs.
    """

    def __init__(self, inbox: list[dict[str, Any]]) -> None:
        self._inbox = list(inbox)
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    async def send_json(self, obj: dict[str, Any]) -> None:
        self.sent.append(obj)

    async def receive_json(self, timeout: float | None = None) -> dict[str, Any]:
        if not self._inbox:
            raise RuntimeError("FakeWS inbox exhausted")
        return self._inbox.pop(0)

    def __aiter__(self) -> "FakeWS":
        return self

    async def __anext__(self) -> _FakeMsg:
        if not self._inbox:
            raise StopAsyncIteration
        return _FakeMsg(self._inbox.pop(0))


def test_encode_auth_header_round_trip() -> None:
    h = _encode_auth_header("api.example.com", "TOKEN")
    decoded = json.loads(base64.urlsafe_b64decode(h + "==").decode("utf-8"))
    assert decoded == {"host": "api.example.com", "Authorization": "TOKEN"}


def test_ws_connect_url_has_required_query_params() -> None:
    url = _ws_connect_url(
        "wss://realtime.example.com/graphql", "api.example.com", "TOKEN"
    )
    assert url.startswith("wss://realtime.example.com/graphql?")
    qs = url.split("?", 1)[1]
    assert "header=" in qs
    assert "payload=" in qs


async def test_ws_handshake_accepts_ack() -> None:
    ws = FakeWS([{"type": "connection_ack", "payload": {"connectionTimeoutMs": 1}}])
    await _ws_handshake(ws, 1.0)  # type: ignore[arg-type]
    assert ws.sent == [{"type": "connection_init"}]


async def test_ws_handshake_rejects_garbage() -> None:
    ws = FakeWS([{"type": "connection_error", "payload": {"errors": ["nope"]}}])
    with pytest.raises(GemstoneApiError):
        await _ws_handshake(ws, 1.0)  # type: ignore[arg-type]


async def test_ws_start_emits_authorized_payload() -> None:
    ws = FakeWS([{"type": "start_ack", "id": "sub-1"}])
    await _ws_start(
        ws,  # type: ignore[arg-type]
        "sub-1",
        "subscription OnX($id: ID!) { onX(id: $id) { id } }",
        {"id": "dev-1"},
        "OnX",
        "api.example.com",
        "TOKEN",
        1.0,
    )
    sent = ws.sent[0]
    assert sent["id"] == "sub-1"
    assert sent["type"] == "start"
    inner = json.loads(sent["payload"]["data"])
    assert inner["query"].startswith("subscription")
    assert inner["variables"] == {"id": "dev-1"}
    assert inner["operationName"] == "OnX"
    auth = sent["payload"]["extensions"]["authorization"]
    assert auth == {"host": "api.example.com", "Authorization": "TOKEN"}


async def test_ws_start_raises_on_error() -> None:
    ws = FakeWS(
        [{"type": "error", "id": "sub-1", "payload": {"errors": ["bad query"]}}]
    )
    with pytest.raises(GemstoneApiError):
        await _ws_start(
            ws,  # type: ignore[arg-type]
            "sub-1",
            "subscription { x }",
            None,
            None,
            "api.example.com",
            "TOKEN",
            1.0,
        )


async def test_ws_iterate_yields_data_and_skips_ka_and_other_ids() -> None:
    ws = FakeWS(
        [
            {"type": "ka"},
            {"type": "data", "id": "other-sub", "payload": {"data": {"x": 1}}},
            {"type": "data", "id": "sub-1", "payload": {"data": {"x": 2}}},
            {"type": "data", "id": "sub-1", "payload": {"data": {"x": 3}}},
            {"type": "complete", "id": "sub-1"},
            {"type": "data", "id": "sub-1", "payload": {"data": {"x": 999}}},
        ]
    )
    events = []
    async for ev in _ws_iterate(ws, "sub-1"):  # type: ignore[arg-type]
        events.append(ev)
    assert events == [{"x": 2}, {"x": 3}]


async def test_ws_iterate_raises_on_error_frame() -> None:
    ws = FakeWS(
        [
            {"type": "error", "id": "sub-1", "payload": {"errors": ["server boom"]}},
        ]
    )
    with pytest.raises(GemstoneApiError):
        async for _ in _ws_iterate(ws, "sub-1"):  # type: ignore[arg-type]
            pass


# ---------------------------------------------------------------------------
# GraphQL HTTP surface, exercised via GemstoneClient.graphql / introspect.
# Reuses the same fake-tokens fixture as the REST tests.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_tokens() -> TokenSet:
    return TokenSet(
        access_token="ACCESS",
        id_token="ID",
        refresh_token="REFRESH",
        expires_at=time.time() + 3600,
    )


@pytest.fixture
async def gc(fake_tokens: TokenSet):
    async with GemstoneClient("test@example.com", "pw") as client:
        client.auth._tokens = fake_tokens

        async def _no_refresh() -> TokenSet:
            return fake_tokens

        client.auth.ensure_fresh = _no_refresh  # type: ignore[method-assign]
        yield client


@pytest.mark.rest
async def test_graphql_returns_data(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.post(
            APPSYNC_API_URL,
            payload={"data": {"hello": "world"}},
        )
        result = await gc.graphql("query { hello }")
    assert result == {"hello": "world"}


@pytest.mark.rest
async def test_graphql_uses_id_token_no_bearer(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.post(APPSYNC_API_URL, payload={"data": {}})
        await gc.graphql("query { __typename }")
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["headers"]["Authorization"] == "ID"


@pytest.mark.rest
async def test_graphql_raises_on_errors_array(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.post(
            APPSYNC_API_URL,
            payload={"errors": [{"message": "Field 'nope' not found"}]},
        )
        with pytest.raises(GemstoneApiError):
            await gc.graphql("query { nope }")


@pytest.mark.rest
async def test_introspect_returns_empty_when_disabled(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.post(APPSYNC_API_URL, status=403, body="introspection disabled")
        result = await gc.introspect_schema()
    assert result == {}


@pytest.mark.rest
async def test_introspect_sends_introspection_query(gc: GemstoneClient) -> None:
    with aioresponses() as m:
        m.post(APPSYNC_API_URL, payload={"data": {"__schema": {"types": []}}})
        result = await gc.introspect_schema()
    assert "__schema" in result
    req = next(iter(m.requests.values()))[0]
    assert req.kwargs["json"]["query"] == INTROSPECTION_QUERY
