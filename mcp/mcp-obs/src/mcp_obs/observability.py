"""HTTP client for VictoriaLogs and VictoriaTraces APIs."""

from __future__ import annotations

import json
from typing import Any

import httpx


class ObservabilityClient:
    """Client for VictoriaLogs and VictoriaTraces HTTP APIs."""

    def __init__(self, victorialogs_url: str, victoriatraces_url: str) -> None:
        self.victorialogs_url = victorialogs_url.rstrip("/")
        self.victoriatraces_url = victoriatraces_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    # ── VictoriaLogs ──────────────────────────────────────────────

    async def logs_search(self, query: str, limit: int = 50) -> str:
        """Search VictoriaLogs using LogsQL."""
        url = f"{self.victorialogs_url}/select/logsql/query"
        resp = await self._client.get(url, params={"query": query, "limit": limit})
        resp.raise_for_status()
        # VictoriaLogs returns newline-delimited JSON objects
        lines = resp.text.strip().split("\n")
        results = []
        for line in lines:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    results.append({"_raw": line})
        if not results:
            return "No log entries found for the given query."
        return json.dumps(results, ensure_ascii=False, indent=2)

    async def logs_error_count(self, minutes: int = 60, service: str | None = None) -> str:
        """Count error-level log entries over a time window."""
        time_filter = f"_time:{minutes}m"
        severity_filter = "severity:ERROR"
        parts = [time_filter, severity_filter]
        if service:
            parts.append(f'service.name:"{service}"')
        query = " ".join(parts)
        url = f"{self.victorialogs_url}/select/logsql/query"
        resp = await self._client.get(url, params={"query": query, "limit": 10000})
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        count = sum(1 for line in lines if line.strip())
        return json.dumps({"error_count": count, "window_minutes": minutes, "service": service or "all"})

    # ── VictoriaTraces (Jaeger-compatible API) ────────────────────

    async def traces_list(self, service: str, limit: int = 20) -> str:
        """List recent traces for a service."""
        url = f"{self.victoriatraces_url}/select/jaeger/api/traces"
        resp = await self._client.get(url, params={"service": service, "limit": limit})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return f"No traces found for service '{service}'."
        # Summarize trace list
        traces = data if isinstance(data, list) else data.get("data", [])
        summary = []
        for trace in traces[:limit]:
            trace_id = trace.get("traceID", "unknown")
            spans = trace.get("spans", [])
            start_time = spans[0].get("startTime", 0) if spans else 0
            summary.append({
                "trace_id": trace_id,
                "span_count": len(spans),
                "start_time_micros": start_time,
            })
        return json.dumps({"traces": summary, "total": len(traces)}, ensure_ascii=False, indent=2)

    async def traces_get(self, trace_id: str) -> str:
        """Fetch a specific trace by ID."""
        url = f"{self.victoriatraces_url}/select/jaeger/api/traces/{trace_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return f"No trace found with ID '{trace_id}'."
        # Summarize the trace
        traces = data.get("data", []) if isinstance(data, dict) else data
        if not traces:
            return f"No trace data found for ID '{trace_id}'."
        trace = traces[0]
        spans = trace.get("spans", [])
        span_summary = []
        for span in spans:
            span_summary.append({
                "span_id": span.get("spanID", "unknown"),
                "operation": span.get("operationName", "unknown"),
                "service": span.get("processID", ""),
                "duration_micros": span.get("duration", 0),
                "tags_count": len(span.get("tags", [])),
            })
        # Resolve process IDs to service names
        processes = trace.get("processes", {})
        service_map = {pid: proc.get("serviceName", pid) for pid, proc in processes.items()}
        for s in span_summary:
            s["service"] = service_map.get(s["service"], s["service"])
        return json.dumps({
            "trace_id": trace.get("traceID", trace_id),
            "span_count": len(spans),
            "spans": span_summary,
        }, ensure_ascii=False, indent=2)

    async def __aenter__(self) -> "ObservabilityClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
