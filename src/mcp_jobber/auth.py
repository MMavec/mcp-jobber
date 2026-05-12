"""Jobber authentication: OAuth 2 code flow with refresh, plus PAT fallback."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Settings

TOKEN_REFRESH_MARGIN_SECONDS = 60


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at: float  # epoch seconds

    def is_fresh(self, *, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return self.access_token != "" and self.expires_at - now > TOKEN_REFRESH_MARGIN_SECONDS

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> TokenBundle:
        data = json.loads(raw)
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data["expires_at"]),
        )


class JobberAuth:
    """Coordinates access-token issuance for the GraphQL client.

    OAuth flow: swaps the configured refresh_token for an access_token, then
    re-uses it until it is within TOKEN_REFRESH_MARGIN_SECONDS of expiry. The
    token cache is persisted to disk so restarts do not burn a refresh.

    PAT flow (JOBBER_PAT): the supplied bearer token is returned verbatim; no
    refresh. Jobber issues no long-lived personal tokens, so this is for quick
    local use with an access token obtained out of band.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.mode = settings.auth_mode()
        self._http = http_client
        self._owns_http = http_client is None
        self._lock = asyncio.Lock()
        self._bundle: TokenBundle | None = None
        if self.mode == "oauth":
            self._load_cached_bundle()

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get_access_token(self) -> str:
        if self.mode == "pat":
            assert self.settings.pat is not None
            return self.settings.pat

        async with self._lock:
            if self._bundle is None or not self._bundle.is_fresh():
                await self._refresh_locked()
            assert self._bundle is not None
            return self._bundle.access_token

    async def _refresh_locked(self) -> None:
        settings = self.settings
        if not (settings.client_id and settings.client_secret):
            raise RuntimeError("OAuth refresh requires client_id and client_secret")

        refresh_token = (
            self._bundle.refresh_token if self._bundle and self._bundle.refresh_token else settings.refresh_token
        )
        if not refresh_token:
            raise RuntimeError("No refresh_token available for OAuth refresh")

        http = self._get_http()
        resp = await http.post(
            settings.oauth_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Jobber OAuth refresh failed ({resp.status_code}): {resp.text}"
            )
        payload = resp.json()

        self._bundle = TokenBundle(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token", refresh_token),
            expires_at=time.time() + float(payload.get("expires_in", 3600)),
        )
        self._save_cached_bundle()

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        return self._http

    def _cache_path(self) -> Path:
        return self.settings.resolved_token_cache()

    def _load_cached_bundle(self) -> None:
        path = self._cache_path()
        if not path.exists():
            return
        try:
            self._bundle = TokenBundle.from_json(path.read_text())
        except (OSError, ValueError, KeyError):
            self._bundle = None

    def _save_cached_bundle(self) -> None:
        if self._bundle is None:
            return
        path = self._cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._bundle.to_json())
            path.chmod(0o600)
        except OSError:
            pass
