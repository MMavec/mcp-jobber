"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOBBER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_url: str = "https://api.getjobber.com/api/graphql"
    oauth_authorize_url: str = "https://api.getjobber.com/api/oauth/authorize"
    oauth_token_url: str = "https://api.getjobber.com/api/oauth/token"
    # Sent as the required X-JOBBER-GRAPHQL-VERSION header. Must be a date string
    # that Jobber currently publishes as active; see developer.getjobber.com/docs/changelog.
    graphql_version: str = "2025-04-16"

    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    redirect_uri: str = "http://localhost:8976/callback"

    pat: str | None = None

    token_cache: Path = Field(default=Path("~/.cache/mcp-jobber/tokens.json"))

    rate_capacity: int = 2500
    rate_window_seconds: int = 300

    request_timeout_seconds: float = 30.0

    def resolved_token_cache(self) -> Path:
        return self.token_cache.expanduser()

    def auth_mode(self) -> str:
        if self.refresh_token and self.client_id and self.client_secret:
            return "oauth"
        if self.pat:
            return "pat"
        raise RuntimeError(
            "No Jobber credentials configured. Set JOBBER_CLIENT_ID + "
            "JOBBER_CLIENT_SECRET + JOBBER_REFRESH_TOKEN, or JOBBER_PAT."
        )


def load_settings() -> Settings:
    return Settings()
