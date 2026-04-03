"""Settings for the observability MCP server."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class ObsSettings(BaseSettings):
    victorialogs_url: str = "http://localhost:9428"
    victoriatraces_url: str = "http://localhost:10428"


def resolve_settings() -> ObsSettings:
    return ObsSettings()
