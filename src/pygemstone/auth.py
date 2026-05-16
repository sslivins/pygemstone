"""Cognito SRP authentication wrapper for Gemstone Lights.

Gemstone's mobile app uses AWS Cognito User Pools with the
``USER_SRP_AUTH`` flow — no plaintext password ever crosses the wire.
We delegate the actual SRP math to :mod:`pycognito`, which is widely
used and battle-tested, then expose an async surface by running each
synchronous call in a thread.

The :class:`GemstoneAuth` object owns the access / id / refresh
tokens and refreshes them transparently before expiry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from .const import COGNITO_CLIENT_ID, COGNITO_USER_POOL_ID, AWS_REGION
from .errors import GemstoneAuthError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TokenSet:
    """Cognito tokens plus the absolute UNIX time the access token expires."""

    access_token: str
    id_token: str
    refresh_token: str
    expires_at: float

    def is_expiring(self, leeway: float = 60.0) -> bool:
        """True if the access token is within ``leeway`` seconds of expiry."""
        return time.time() + leeway >= self.expires_at


class GemstoneAuth:
    """Async-friendly Cognito SRP authenticator.

    Usage::

        auth = GemstoneAuth(email="you@example.com", password="...")
        await auth.login()
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=await auth.bearer_headers()) as r:
                ...

    The instance is safe to share across many concurrent requests; the
    refresh path is serialised by an :class:`asyncio.Lock`.
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        user_pool_id: str = COGNITO_USER_POOL_ID,
        client_id: str = COGNITO_CLIENT_ID,
        region: str = AWS_REGION,
    ) -> None:
        self._email = email
        self._password = password
        self._user_pool_id = user_pool_id
        self._client_id = client_id
        self._region = region
        self._tokens: TokenSet | None = None
        self._lock = asyncio.Lock()

    @property
    def tokens(self) -> TokenSet | None:
        return self._tokens

    async def login(self) -> TokenSet:
        """Run the full SRP login and stash the resulting tokens."""
        async with self._lock:
            self._tokens = await asyncio.to_thread(self._login_sync)
            return self._tokens

    async def logout(self) -> None:
        """Best-effort global sign-out; clears local tokens unconditionally."""
        if self._tokens is None:
            return
        try:
            await asyncio.to_thread(self._logout_sync, self._tokens.access_token)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Cognito global sign-out failed (ignored): %s", exc)
        finally:
            self._tokens = None

    async def ensure_fresh(self) -> TokenSet:
        """Return tokens, refreshing if the access token is near expiry."""
        if self._tokens is None:
            return await self.login()
        if not self._tokens.is_expiring():
            return self._tokens
        async with self._lock:
            # Re-check inside the lock; another waiter may have refreshed.
            tokens = self._tokens
            if tokens is None or tokens.is_expiring():
                tokens = await asyncio.to_thread(
                    self._refresh_sync, tokens.refresh_token if tokens else ""
                )
                self._tokens = tokens
            return tokens

    async def bearer_headers(self) -> dict[str, str]:
        """Headers ready to drop into an ``aiohttp.ClientSession`` request."""
        tokens = await self.ensure_fresh()
        return {"Authorization": f"Bearer {tokens.access_token}"}

    def _login_sync(self) -> TokenSet:
        try:
            from pycognito import Cognito
        except ImportError as exc:  # pragma: no cover - exercised only without dep
            raise GemstoneAuthError(
                "pycognito is required for Gemstone auth. "
                "Install it via `pip install pycognito`."
            ) from exc

        try:
            cog = Cognito(
                user_pool_id=self._user_pool_id,
                client_id=self._client_id,
                user_pool_region=self._region,
                username=self._email,
            )
            cog.authenticate(password=self._password)
        except Exception as exc:  # noqa: BLE001 — pycognito raises various
            raise GemstoneAuthError(f"Cognito SRP auth failed: {exc}") from exc

        return self._tokens_from_cognito(cog)

    def _refresh_sync(self, refresh_token: str) -> TokenSet:
        try:
            from pycognito import Cognito
        except ImportError as exc:  # pragma: no cover
            raise GemstoneAuthError("pycognito is required") from exc

        try:
            cog = Cognito(
                user_pool_id=self._user_pool_id,
                client_id=self._client_id,
                user_pool_region=self._region,
                refresh_token=refresh_token,
            )
            # ``check_token`` would refuse without an access_token to inspect
            # ("Access Token Required to Check Token"); we know we want to
            # refresh so we hit ``renew_access_token`` directly. It uses the
            # refresh_token via REFRESH_TOKEN_AUTH and replaces access/id
            # tokens on the Cognito instance.
            cog.renew_access_token()
        except Exception as exc:  # noqa: BLE001
            raise GemstoneAuthError(f"Token refresh failed: {exc}") from exc

        return self._tokens_from_cognito(cog, refresh_fallback=refresh_token)

    def _logout_sync(self, access_token: str) -> None:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError:
            # boto3 is a transitive dep of pycognito; if it's absent we
            # silently skip the server-side revoke. Local tokens are
            # already being cleared by the caller.
            return

        client = boto3.client("cognito-idp", region_name=self._region)
        try:
            client.global_sign_out(AccessToken=access_token)
        except Exception:  # noqa: BLE001
            # 401 here means the token already expired — fine to ignore.
            pass

    @staticmethod
    def _tokens_from_cognito(
        cog: Any, refresh_fallback: str | None = None
    ) -> TokenSet:
        # pycognito exposes the tokens as plain attributes and also
        # carries a refresh_token only on the initial authenticate; on
        # refresh-only flows we may need to keep using the prior refresh
        # token, hence the fallback.
        access_token = getattr(cog, "access_token", None)
        id_token = getattr(cog, "id_token", None)
        refresh_token = getattr(cog, "refresh_token", None) or refresh_fallback or ""
        if not access_token or not id_token:
            raise GemstoneAuthError(
                "Cognito did not return access/id tokens after authentication."
            )
        # access_token_expiration is a python datetime when present;
        # otherwise we fall back to ``token_expires_in`` (seconds from now).
        exp = getattr(cog, "access_token_expiration", None)
        if exp is not None:
            try:
                expires_at = exp.timestamp()
            except Exception:  # noqa: BLE001
                expires_at = time.time() + 3600
        else:
            expires_at = time.time() + int(getattr(cog, "token_expires_in", 3600))
        return TokenSet(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
