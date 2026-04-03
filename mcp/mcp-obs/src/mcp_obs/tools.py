"""Tool schemas, handlers, and registry for the observability MCP server."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from mcp.types import Tool
from pydantic import BaseModel, Field

from mcp_obs.observability import VictoriaLogsClient, VictoriaTracesClient


class LogSearchArgs(BaseModel):
    query: str = Field(
        description="LogsQL query string, e.g. 'severity:ERROR service.name:\"Learning Management Service\"'"
    )
    limit: int = Field(
        default=20, ge=1, le=200, description="Max log entries to return (default 20)"
    )
    window: str = Field(
        default="1h", description="Time window, e.g. '10m', '1h', '24h'"
    )


class ErrorCountArgs(BaseModel):
    service: str = Field(
        default="",
        description="Service name to count errors for (empty = all services)",
    )
    window: str = Field(
        default="10m", description="Time window for counting errors, e.g. '10m', '1h'"
    )


class TraceListArgs(BaseModel):
    service: str = Field(
        description="Service name to list traces for, e.g. 'Learning Management Service'"
    )
    limit: int = Field(
        default=10, ge=1, le=50, description="Max traces to return (default 10)"
    )


class TraceGetArgs(BaseModel):
    trace_id: str = Field(description="Trace ID to fetch, e.g. 'abc123...'")


ToolPayload = BaseModel | Sequence[BaseModel] | dict | list | str
ToolHandler = Callable[..., Awaitable[ToolPayload]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    model: type[BaseModel]
    handler: ToolHandler

    def as_tool(self) -> Tool:
        schema = self.model.model_json_schema()
        schema.pop("$defs", None)
        schema.pop("title", None)
        return Tool(name=self.name, description=self.description, inputSchema=schema)


async def _logs_search(
    logs: VictoriaLogsClient, _traces: VictoriaTracesClient, args: LogSearchArgs
) -> ToolPayload:
    """Search logs by query and time window."""
    # Prepend time window to query if not already present
    query = args.query
    if "_time:" not in query:
        query = f"_time:{args.window} {query}"

    entries = logs.query_logs(query, limit=args.limit)
    return {
        "query": query,
        "count": len(entries),
        "entries": entries,
    }


async def _logs_error_count(
    logs: VictoriaLogsClient, _traces: VictoriaTracesClient, args: ErrorCountArgs
) -> ToolPayload:
    """Count errors in logs for a service over a time window."""
    service = args.service if args.service else None
    result = logs.count_errors(service=service, window=args.window)
    return result


async def _traces_list(
    logs: VictoriaLogsClient, traces: VictoriaTracesClient, args: TraceListArgs
) -> ToolPayload:
    """List recent traces for a service."""
    trace_list = traces.list_traces(args.service, limit=args.limit)
    return {
        "service": args.service,
        "count": len(trace_list),
        "traces": trace_list,
    }


async def _traces_get(
    logs: VictoriaLogsClient, traces: VictoriaTracesClient, args: TraceGetArgs
) -> ToolPayload:
    """Fetch a specific trace by ID."""
    trace = traces.get_trace(args.trace_id)
    if trace is None:
        return {"error": f"Trace not found: {args.trace_id}"}
    return trace


TOOL_SPECS = (
    ToolSpec(
        "logs_search",
        "Search structured logs by LogsQL query and time window. Use for finding specific log entries or patterns.",
        LogSearchArgs,
        _logs_search,
    ),
    ToolSpec(
        "logs_error_count",
        "Count error-level log entries for a service over a time window. Use first when checking system health.",
        ErrorCountArgs,
        _logs_error_count,
    ),
    ToolSpec(
        "traces_list",
        "List recent traces for a service. Use to find trace IDs or explore recent request patterns.",
        TraceListArgs,
        _traces_list,
    ),
    ToolSpec(
        "traces_get",
        "Fetch full details of a specific trace by ID. Use to inspect the complete request path and span hierarchy.",
        TraceGetArgs,
        _traces_get,
    ),
)
TOOLS_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}
