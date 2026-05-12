"""Thin GraphQL client that wires auth + rate limiter to the Jobber endpoint."""

from __future__ import annotations

from typing import Any

import httpx

from .auth import JobberAuth
from .config import Settings
from .rate_limiter import AsyncTokenBucket


class JobberGraphQLError(RuntimeError):
    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__("; ".join(e.get("message", "unknown") for e in errors))


class JobberClient:
    """Executes GraphQL operations with transparent auth + throttling.

    The rate limiter counts *requests*, not query cost. Jobber additionally
    tracks a point-based cost in response extensions; we surface that back to
    callers by exposing `last_cost` so downstream tools can back off if they
    see the daily allowance draining.
    """

    def __init__(
        self,
        settings: Settings,
        auth: JobberAuth,
        *,
        http_client: httpx.AsyncClient | None = None,
        limiter: AsyncTokenBucket | None = None,
    ) -> None:
        self.settings = settings
        self.auth = auth
        self._http = http_client
        self._owns_http = http_client is None
        self.limiter = limiter or AsyncTokenBucket(
            capacity=settings.rate_capacity,
            window_seconds=float(settings.rate_window_seconds),
        )
        self.last_cost: dict[str, Any] | None = None

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        return self._http

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.limiter.acquire()
        token = await self.auth.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-JOBBER-GRAPHQL-VERSION": self.settings.graphql_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {"query": query, "variables": variables or {}}

        resp = await self._http_client().post(
            self.settings.api_url, headers=headers, json=body
        )

        # Try to decode the body even on errors: Jobber returns a GraphQL
        # `errors` array (with extensions.code == "THROTTLED") alongside HTTP 429.
        try:
            payload = resp.json()
        except ValueError:
            payload = {}

        if isinstance(payload, dict) and payload.get("extensions", {}).get("cost"):
            self.last_cost = payload["extensions"]["cost"]

        if resp.status_code == 429:
            errors = payload.get("errors") if isinstance(payload, dict) else None
            raise JobberGraphQLError(
                errors
                or [{"message": "Jobber rate limit hit (HTTP 429). Back off and retry.",
                     "extensions": {"code": "THROTTLED"}}]
            )
        resp.raise_for_status()

        if payload.get("errors"):
            raise JobberGraphQLError(payload["errors"])
        return payload.get("data") or {}
