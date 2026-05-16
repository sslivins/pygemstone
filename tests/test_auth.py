"""Unit tests for ``pygemstone.auth.GemstoneAuth``.

Cognito SRP is mocked out; we only verify that the right pycognito
methods are called in the right order, and that the resulting
:class:`TokenSet` is populated correctly.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from pygemstone.auth import GemstoneAuth, TokenSet
from pygemstone.errors import GemstoneAuthError


def _fake_cog(
    *,
    access_token: str = "AT",
    id_token: str = "IT",
    refresh_token: str | None = "RT",
    expires_in: int = 3600,
) -> MagicMock:
    """Build a MagicMock that walks like a pycognito.Cognito instance."""
    cog = MagicMock(name="Cognito")
    cog.access_token = access_token
    cog.id_token = id_token
    cog.refresh_token = refresh_token
    cog.access_token_expiration = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in
    )
    cog.token_expires_in = expires_in
    return cog


@pytest.mark.auth
async def test_login_calls_authenticate(monkeypatch: pytest.MonkeyPatch) -> None:
    cog = _fake_cog()
    factory = MagicMock(return_value=cog)
    monkeypatch.setattr("pycognito.Cognito", factory)

    auth = GemstoneAuth("user@example.com", "pw")
    tokens = await auth.login()

    factory.assert_called_once()
    kwargs = factory.call_args.kwargs
    assert kwargs["username"] == "user@example.com"
    cog.authenticate.assert_called_once_with(password="pw")
    assert tokens.access_token == "AT"
    assert tokens.id_token == "IT"
    assert tokens.refresh_token == "RT"
    assert tokens.expires_at > time.time()


@pytest.mark.auth
async def test_login_failure_wraps_in_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = _fake_cog()
    cog.authenticate.side_effect = RuntimeError("Cognito said no")
    monkeypatch.setattr("pycognito.Cognito", MagicMock(return_value=cog))

    auth = GemstoneAuth("user@example.com", "pw")
    with pytest.raises(GemstoneAuthError, match="Cognito SRP auth failed"):
        await auth.login()


@pytest.mark.auth
async def test_ensure_fresh_returns_cached_when_not_expiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = MagicMock()
    monkeypatch.setattr("pycognito.Cognito", factory)

    auth = GemstoneAuth("user@example.com", "pw")
    auth._tokens = TokenSet(
        access_token="AT",
        id_token="IT",
        refresh_token="RT",
        expires_at=time.time() + 3600,
    )

    tokens = await auth.ensure_fresh()
    assert tokens.access_token == "AT"
    factory.assert_not_called()


@pytest.mark.auth
async def test_refresh_uses_renew_access_token_not_check_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: ``_refresh_sync`` must call ``renew_access_token``.

    Calling ``check_token`` on a ``Cognito`` instance with no access
    token raises ``AttributeError("Access Token Required to Check
    Token")`` inside pycognito. We construct the instance with only a
    refresh_token, so ``renew_access_token`` is the only path that
    works.
    """
    refreshed = _fake_cog(access_token="AT2", id_token="IT2", refresh_token=None)
    factory = MagicMock(return_value=refreshed)
    monkeypatch.setattr("pycognito.Cognito", factory)

    auth = GemstoneAuth("user@example.com", "pw")
    auth._tokens = TokenSet(
        access_token="AT",
        id_token="IT",
        refresh_token="RT",
        expires_at=time.time() - 10,  # already expired
    )

    tokens = await auth.ensure_fresh()

    # Refresh path: built a Cognito with refresh_token, called renew_access_token.
    assert factory.call_args.kwargs["refresh_token"] == "RT"
    refreshed.renew_access_token.assert_called_once_with()
    refreshed.check_token.assert_not_called()
    # check_token is the wrong API; make sure we never call it on the refresh path.
    assert tokens.access_token == "AT2"
    assert tokens.id_token == "IT2"
    # pycognito doesn't return a new refresh_token on REFRESH_TOKEN_AUTH; we
    # keep the prior one.
    assert tokens.refresh_token == "RT"


@pytest.mark.auth
async def test_refresh_failure_wraps_in_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = _fake_cog()
    cog.renew_access_token.side_effect = RuntimeError("Refresh Token has been revoked")
    monkeypatch.setattr("pycognito.Cognito", MagicMock(return_value=cog))

    auth = GemstoneAuth("user@example.com", "pw")
    auth._tokens = TokenSet(
        access_token="AT",
        id_token="IT",
        refresh_token="RT",
        expires_at=time.time() - 10,
    )

    with pytest.raises(GemstoneAuthError, match="Token refresh failed"):
        await auth.ensure_fresh()


@pytest.mark.auth
async def test_bearer_headers_returns_bearer_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = GemstoneAuth("user@example.com", "pw")
    auth._tokens = TokenSet(
        access_token="ABC",
        id_token="DEF",
        refresh_token="GHI",
        expires_at=time.time() + 3600,
    )
    monkeypatch.setattr("pycognito.Cognito", MagicMock())

    headers = await auth.bearer_headers()
    assert headers == {"Authorization": "Bearer ABC"}


@pytest.mark.auth
async def test_tokens_from_cognito_falls_back_when_no_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If pycognito doesn't expose ``access_token_expiration`` we should
    still produce a sensible ``expires_at`` from ``token_expires_in``.
    """
    cog = _fake_cog(expires_in=1800)
    del cog.access_token_expiration  # force the fallback path
    monkeypatch.setattr("pycognito.Cognito", MagicMock(return_value=cog))

    auth = GemstoneAuth("user@example.com", "pw")
    tokens = await auth.login()
    assert 1500 < tokens.expires_at - time.time() <= 1800
