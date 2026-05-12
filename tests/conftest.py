"""Shared fixtures: a fake Jobber GraphQL endpoint driven by httpx.MockTransport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from mcp_jobber.auth import JobberAuth
from mcp_jobber.client import JobberClient
from mcp_jobber.config import Settings
from mcp_jobber.rate_limiter import AsyncTokenBucket
from mcp_jobber.server import build_server


class FakeJobber:
    """Programmable stand-in for api.getjobber.com.

    Tests register responses via `.respond_to(operation_name, payload)`. The
    transport dispatches based on the first word after `query`/`mutation` in
    the GraphQL document, so tests can assert on per-operation behaviour
    without pinning the exact query string.
    """

    def __init__(self) -> None:
        self._responses: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[dict[str, Any]] = []
        self.token_responses: list[dict[str, Any]] = []

    def respond_to(self, operation_name: str, data: dict[str, Any]) -> None:
        self._responses.setdefault(operation_name, []).append({"data": data})

    def respond_error(self, operation_name: str, errors: list[dict[str, Any]]) -> None:
        self._responses.setdefault(operation_name, []).append({"errors": errors})

    def queue_token_response(self, *, access: str = "at-1", refresh: str = "rt-1", expires_in: int = 3600) -> None:
        self.token_responses.append(
            {"access_token": access, "refresh_token": refresh, "expires_in": expires_in}
        )

    def _pick_operation(self, query: str) -> str:
        for keyword in ("query", "mutation"):
            idx = query.find(keyword)
            if idx >= 0:
                tail = query[idx + len(keyword) :].strip()
                name = tail.split("(")[0].split("{")[0].strip()
                if name:
                    return name
        return "anonymous"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            body = self.token_responses.pop(0) if self.token_responses else {
                "access_token": "at-default",
                "refresh_token": "rt-default",
                "expires_in": 3600,
            }
            return httpx.Response(200, json=body)

        assert request.url.path.endswith("/graphql"), f"unexpected URL {request.url}"
        payload = json.loads(request.content.decode())
        op = self._pick_operation(payload["query"])
        self.calls.append(
            {
                "operation": op,
                "variables": payload.get("variables"),
                "headers": dict(request.headers),
            }
        )
        queue = self._responses.get(op)
        if not queue:
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(200, json=queue.pop(0))


@pytest.fixture
def fake_jobber() -> FakeJobber:
    return FakeJobber()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rt-seed",
        token_cache=tmp_path / "tokens.json",
        rate_capacity=2500,
        rate_window_seconds=300,
    )


@pytest.fixture
def pat_settings(tmp_path: Path) -> Settings:
    return Settings(
        pat="pat-xyz",
        token_cache=tmp_path / "tokens.json",
    )


@pytest.fixture
async def http_client(fake_jobber: FakeJobber):
    transport = httpx.MockTransport(fake_jobber.handler)
    async with httpx.AsyncClient(transport=transport) as c:
        yield c


@pytest.fixture
async def jobber_client(settings: Settings, fake_jobber: FakeJobber, http_client: httpx.AsyncClient):
    # Seed an OAuth refresh response so the first call succeeds.
    fake_jobber.queue_token_response()
    auth = JobberAuth(settings, http_client=http_client)
    # Large bucket so rate limiter never trips in tests.
    limiter = AsyncTokenBucket(capacity=10_000, window_seconds=1.0)
    client = JobberClient(settings, auth, http_client=http_client, limiter=limiter)
    yield client
    await client.aclose()
    await auth.aclose()


@pytest.fixture
def mcp_server(settings: Settings, jobber_client: JobberClient):
    return build_server(settings=settings, client=jobber_client)
