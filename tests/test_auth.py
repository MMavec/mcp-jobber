"""Auth tests: OAuth refresh + cache, PAT fallback, missing-creds error."""

from __future__ import annotations

import time

import pytest

from mcp_jobber.auth import JobberAuth, TokenBundle
from mcp_jobber.config import Settings


async def test_pat_mode_returns_token_verbatim(pat_settings: Settings):
    auth = JobberAuth(pat_settings)
    assert await auth.get_access_token() == "pat-xyz"


async def test_oauth_refresh_exchanges_refresh_token(settings, fake_jobber, http_client):
    fake_jobber.queue_token_response(access="live-access", refresh="new-refresh")
    auth = JobberAuth(settings, http_client=http_client)

    token = await auth.get_access_token()
    assert token == "live-access"
    # Reused from cache on a second call; only one token request should fire.
    token2 = await auth.get_access_token()
    assert token2 == "live-access"


async def test_oauth_refreshes_when_expired(settings, fake_jobber, http_client):
    fake_jobber.queue_token_response(access="first", expires_in=1)
    fake_jobber.queue_token_response(access="second", expires_in=3600)
    auth = JobberAuth(settings, http_client=http_client)

    assert await auth.get_access_token() == "first"
    # Force expiry.
    auth._bundle = TokenBundle(access_token="first", refresh_token="rt-seed", expires_at=time.time() - 5)
    assert await auth.get_access_token() == "second"


async def test_token_cache_round_trip(settings, fake_jobber, http_client):
    fake_jobber.queue_token_response(access="persisted")
    auth = JobberAuth(settings, http_client=http_client)
    await auth.get_access_token()
    assert settings.resolved_token_cache().exists()

    # New auth instance: should load cache and skip the network.
    auth2 = JobberAuth(settings, http_client=http_client)
    assert await auth2.get_access_token() == "persisted"


async def test_missing_credentials_raises(tmp_path):
    settings = Settings(token_cache=tmp_path / "tokens.json")
    with pytest.raises(RuntimeError, match="No Jobber credentials"):
        JobberAuth(settings)
