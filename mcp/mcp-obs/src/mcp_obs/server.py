"""Stdio MCP server exposing observability operations as typed tools."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from mcp_obs.observability import ObservabilityClient
from mcp_obs.settings import resolve_settings


# ── Tool input models ─────────────────────────────────────────────

class LogsSearchParams(BaseModel):
    query: str = Field(description="LogsQL query string. Example: `_time:10m service.name:\"Learning Management Service\" severity:ERROR`")
    limit: int = Field(default=50, description="Maximum number of log entries to return")


class LogsErrorCountParams(BaseModel):
    minutes: int = Field(default=60, description="Time window in minutes to look back for errors")
    service: str = Field(default="", description="Optional service name filter. Leave empty for all services.")


class TracesListParams(BaseModel):
    service: str = Field(description="Service name to list traces for. Example: 'Learning Management Service'")
    limit: int = Field(default=20, description="Maximum number of traces to return")


class TracesGetParams(BaseModel):
    trace_id: str = Field(description="Trace ID to fetch. Example: '42207ed3ce60f27af280d9b49b39892e'")


# ── Tool registry ─────────────────────────────────────────────────

TOOLS = [
    (
        "logs_search",
        "Search structured logs in VictoriaLogs using LogsQL. Use this to find specific log entries by service, severity, event, or keyword. Always include a _time filter like `_time:10m` to narrow the window.",
        LogsSearchParams,
    ),
    (
        "logs_error_count",
        "Count error-level log entries over a recent time window. Use this first when asked about errors to quickly gauge severity before diving into details with logs_search.",
        LogsErrorCountParams,
    ),
    (
        "traces_list",
        "List recent traces for a given service. Use this to find trace IDs that can then be fetched in detail with traces_get.",
        TracesListParams,
    ),
    (
        "traces_get",
        "Fetch a specific trace by ID. Returns span hierarchy with service names, operations, and durations. Use this after finding a trace_id from logs or traces_list.",
        TracesGetParams,
    ),
]


def create_server(client: ObservabilityClient) -> Server:
    server = Server("observability")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name=name, description=desc, inputSchema=schema.model_json_schema())
            for name, desc, schema in TOOLS
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[TextContent]:
        try:
            if name == "logs_search":
                params = LogsSearchParams.model_validate(arguments or {})
                result = await client.logs_search(params.query, params.limit)
            elif name == "logs_error_count":
                params = LogsErrorCountParams.model_validate(arguments or {})
                svc = params.service if params.service else None
                result = await client.logs_error_count(params.minutes, svc)
            elif name == "traces_list":
                params = TracesListParams.model_validate(arguments or {})
                result = await client.traces_list(params.service, params.limit)
            elif name == "traces_get":
                params = TracesGetParams.model_validate(arguments or {})
                result = await client.traces_get(params.trace_id)
            else:
                result = f"Unknown tool: {name}"
        except Exception as exc:
            result = f"Error: {type(exc).__name__}: {exc}"
        return [TextContent(type="text", text=str(result))]

    _ = list_tools, call_tool
    return server


async def main() -> None:
    settings = resolve_settings()
    async with ObservabilityClient(settings.victorialogs_url, settings.victoriatraces_url) as client:
        server = create_server(client)
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
