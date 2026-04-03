"""MCP server for VictoriaLogs and VictoriaTraces."""

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field


class LogsQuery(BaseModel):
    """Query VictoriaLogs."""
    query: str = Field(
        ...,
        description=(
            "LogsQL query string. Use _time for windows (e.g., _time:10m), "
            'service.name for filtering (use FULL names in quotes: "Learning Management Service", '
            '"nanobot", "mcp-lms", "postgres" — NOT short names like "lms"), '
            "severity (ERROR/WARN/INFO/DEBUG), event, trace_id. "
            'Example: _time:10m service.name:"Learning Management Service" severity:ERROR'
        ),
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return")


class LogsErrorCountQuery(BaseModel):
    """Count errors in VictoriaLogs."""
    service: str = Field(
        ...,
        description=(
            "Service name to filter errors. Use the FULL name, NOT a short alias. "
            'Valid names: "Learning Management Service" (LMS backend), "nanobot", '
            '"mcp-lms", "mcp-obs", "postgres".'
        ),
    )
    time_window: str = Field(default="10m", description="Time window for error count (e.g., 10m, 1h)")


class TraceQuery(BaseModel):
    """Query VictoriaTraces."""
    service: str = Field(
        ...,
        description=(
            "Service name to filter traces. Use the FULL name, NOT a short alias. "
            'Valid names: "Learning Management Service", "nanobot", "mcp-lms", "mcp-obs", "postgres".'
        ),
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max traces to return")


class TraceByIdQuery(BaseModel):
    """Get trace by ID."""
    trace_id: str = Field(..., description="The trace ID to look up")


def _text(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, default=str))]


def create_server(logs_url: str, traces_url: str) -> Server:
    server = Server("obs")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="obs_logs_query",
                description=(
                    "Query VictoriaLogs using LogsQL. Use _time for time windows, "
                    'service.name with FULL names in quotes (e.g., "Learning Management Service"), '
                    "severity, event, trace_id. See the query field schema for valid service names."
                ),
                inputSchema=LogsQuery.model_json_schema(),
            ),
            Tool(
                name="obs_logs_error_count",
                description=(
                    "Count errors for a specific service in VictoriaLogs over a time window. "
                    'Use the FULL service name: "Learning Management Service" for the LMS backend, '
                    'NOT "lms".'
                ),
                inputSchema=LogsErrorCountQuery.model_json_schema(),
            ),
            Tool(
                name="obs_traces_list",
                description=(
                    "List recent traces for a service from VictoriaTraces. "
                    'Use the FULL service name: "Learning Management Service" for the LMS backend.'
                ),
                inputSchema=TraceQuery.model_json_schema(),
            ),
            Tool(
                name="obs_traces_get",
                description="Get a specific trace by ID from VictoriaTraces. Use the trace_id from log records.",
                inputSchema=TraceByIdQuery.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        async with httpx.AsyncClient() as client:
            try:
                if name == "obs_logs_query":
                    args = LogsQuery.model_validate(arguments or {})
                    url = f"{logs_url}/select/logsql/query"
                    resp = await client.post(url, params={"query": args.query, "limit": args.limit})
                    resp.raise_for_status()
                    body = resp.text.strip()
                    if not body:
                        return _text({"query": args.query, "results": [], "note": "No logs matched this query."})
                    # VictoriaLogs returns newline-delimited JSON (one JSON object per line)
                    lines = [line.strip() for line in body.split("\n") if line.strip()]
                    results = []
                    for line in lines:
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            results.append(line)
                    return _text({"query": args.query, "results": results, "count": len(results)})

                elif name == "obs_logs_error_count":
                    args = LogsErrorCountQuery.model_validate(arguments or {})
                    query = f'_time:{args.time_window} service.name:"{args.service}" severity:ERROR'
                    url = f"{logs_url}/select/logsql/query"
                    resp = await client.post(url, params={"query": query, "limit": 1000})
                    resp.raise_for_status()
                    body = resp.text.strip()
                    if not body:
                        return _text({
                            "service": args.service,
                            "time_window": args.time_window,
                            "error_count": 0,
                            "sample_errors": [],
                            "note": "No errors found in this time window.",
                        })
                    lines = [line.strip() for line in body.split("\n") if line.strip()]
                    logs = []
                    for line in lines:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            logs.append(line)
                    return _text({
                        "service": args.service,
                        "time_window": args.time_window,
                        "error_count": len(logs),
                        "sample_errors": logs[:5],
                    })

                elif name == "obs_traces_list":
                    args = TraceQuery.model_validate(arguments or {})
                    url = f"{traces_url}/select/jaeger/api/traces"
                    resp = await client.get(url, params={"service": args.service, "limit": args.limit})
                    resp.raise_for_status()
                    body = resp.text.strip()
                    if not body:
                        return _text({"service": args.service, "traces": [], "note": "No traces found for this service."})
                    return _text(resp.json())

                elif name == "obs_traces_get":
                    args = TraceByIdQuery.model_validate(arguments or {})
                    url = f"{traces_url}/select/jaeger/api/traces/{args.trace_id}"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    body = resp.text.strip()
                    if not body:
                        return _text({"trace_id": args.trace_id, "note": "Trace not found."})
                    return _text(resp.json())

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except httpx.HTTPError as e:
                return [TextContent(type="text", text=f"HTTP error: {type(e).__name__}: {e}")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]

    _ = list_tools, call_tool
    return server


async def main(logs_url: str | None = None, traces_url: str | None = None) -> None:
    logs_url = logs_url or "http://victorialogs:9428"
    traces_url = traces_url or "http://victoriatraces:10428"
    server = create_server(logs_url, traces_url)
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
