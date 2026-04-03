---
name: observability
description: Use observability MCP tools to investigate errors and system health
always: true
---

# Observability Skill

You have access to observability tools that let you query structured logs and distributed traces from VictoriaLogs and VictoriaTraces. Use these when the user asks about errors, system health, failures, or "what went wrong."

## Available Tools

| Tool | Description |
|------|-------------|
| `logs_error_count` | Count error-level log entries over a recent time window. Use this first to gauge error severity. |
| `logs_search` | Search structured logs in VictoriaLogs using LogsQL. Always include a `_time` filter like `_time:10m`. |
| `traces_list` | List recent traces for a service. Use to find trace IDs. |
| `traces_get` | Fetch a specific trace by ID. Returns span hierarchy with services, operations, and durations. |

## Investigation Strategy

### When asked "What went wrong?" or "Check system health":

1. **Start with `logs_error_count`** on a narrow recent window (e.g., 10 minutes) to see if there are errors and how many.
2. **If errors exist, use `logs_search`** scoped to the most likely failing service. A good query:
   ```
   _time:10m service.name:"Learning Management Service" severity:ERROR
   ```
3. **Extract a `trace_id`** from the log results if one is present.
4. **Use `traces_get`** with that trace ID to inspect the full request span hierarchy.
5. **Summarize findings concisely** — mention:
   - What the logs show (service, error type, timestamp)
   - What the trace reveals (which span failed, how long it took)
   - Your conclusion about the root cause

### When asked "Any errors in the last N minutes?":

1. Call `logs_error_count` with the specified minutes.
2. If count > 0, call `logs_search` with `_time:Nm severity:ERROR` to inspect details.
3. Report findings concisely — don't dump raw JSON.

### When asked about a specific service:

1. Scope your queries to that service using `service.name:"Service Name"`.
2. Check both error counts and recent traces.

## Response Guidelines

- **Never dump raw JSON** — summarize key findings in natural language.
- **Mention evidence sources** — e.g., "Logs show... The trace confirms..."
- **Be concise** — 2-4 sentences for a healthy system, 4-8 for an error investigation.
- **If no errors found**, say the system looks healthy for the given time window.
- **When the user asks about system health without a time window**, default to the last 10 minutes.

## Field Names

The real field names in this stack are:
- `service.name` — e.g., "Learning Management Service", "nanobot", "Qwen Code API"
- `severity` — e.g., ERROR, INFO, WARN
- `event` — e.g., "request_started", "db_query", "request_completed"
- `trace_id` — hex string used to fetch full traces
