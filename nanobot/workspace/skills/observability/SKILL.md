# Observability Skill

You have access to observability tools that query VictoriaLogs and VictoriaTraces. Use them when the user asks about system health, errors, logs, or traces.

## When to use observability tools

- **"What went wrong?"** or **"Check system health"** → Run a full investigation (see Investigation Flow below)
- **"Any errors in the last X?"** → Use `obs_logs_error_count` first to see if there are errors, then `obs_logs_query` to inspect them
- **"Show me logs for X"** → Use `obs_logs_query` with a LogsQL filter
- **"What happened to request X?"** → Use `obs_logs_query` to find the `trace_id`, then `obs_traces_get` to fetch the full trace
- **"Show recent traces for X"** → Use `obs_traces_list`

## Investigation Flow — "What went wrong?" / "Check system health"

When the user asks you to investigate a problem, follow this sequence in one pass:

1. **Count errors** — call `obs_logs_error_count` for `"Learning Management Service"` with time window `10m`
2. **Search error logs** — call `obs_logs_query` with `_time:10m service.name:"Learning Management Service" severity:ERROR`
3. **Extract trace_id** — from the error log results, pick a `trace_id` field
4. **Fetch the trace** — call `obs_traces_get` with that trace_id
5. **Summarize** — write a coherent explanation that cites BOTH log evidence AND trace evidence. Name:
   - What service failed
   - What the root cause was (e.g., database connection refused)
   - What HTTP status was returned to the user
   - Whether the error message was accurate or misleading

Do NOT dump raw JSON. Write a short narrative: "Error logs show X at [time]. Trace Y confirms the request failed at Z. The backend returned [status] with message [msg]."

## Service names in this deployment

The actual `service.name` values used in this stack:
- `"Learning Management Service"` — the LMS backend (NOT "lms")
- `"nanobot"` — the nanobot gateway
- `"mcp-lms"` — the LMS MCP server
- `"mcp-obs"` — the observability MCP server
- `"mcp-webchat"` — the webchat MCP server
- `"postgres"` — PostgreSQL database

Always use the full service name in quotes for VictoriaLogs queries, e.g.:
```
_time:10m service.name:"Learning Management Service" severity:ERROR
```

## Query patterns

### Logs

VictoriaLogs uses LogsQL. Useful fields:
- `service.name` — e.g., `"Learning Management Service"`, `"nanobot"` (use full names in quotes)
- `severity` — `ERROR`, `WARN`, `INFO`, `DEBUG`
- `event` — e.g., `request_started`, `db_query`, `request_completed`
- `trace_id` — links to traces
- `_time` — time window, e.g., `_time:10m`, `_time:1h`

Example queries:
```
_time:10m service.name:"Learning Management Service" severity:ERROR
_time:1h event:db_query severity:ERROR
```

### Traces

VictoriaTraces uses the Jaeger-compatible API. Query by service name to list traces, or by trace ID to get a specific trace.

## How to answer

1. **Scope your query** — prefer narrow time windows (e.g., "last 10 minutes") and specific services (e.g., LMS backend)
2. **Summarize, don't dump** — tell the user what you found in plain language, not raw JSON
3. **Connect logs to traces** — if you find a `trace_id` in error logs, fetch that trace for the full picture
4. **Be actionable** — if there are errors, say what service failed and what the error was

## Example reasoning flow

User: "Any LMS backend errors in the last 10 minutes?"

1. Call `obs_logs_error_count` with service="Learning Management Service" and time window=10m
2. If errors exist, call `obs_logs_query` with `_time:10m service.name:"Learning Management Service" severity:ERROR`
3. Extract any `trace_id` from error logs
4. Call `obs_traces_get` with the trace_id to see the full request path
5. Summarize: "Yes, there were 3 errors in the last 10 minutes. The LMS backend failed to connect to PostgreSQL — connection refused at [timestamp]. Trace ID: xxx."
