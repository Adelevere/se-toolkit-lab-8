"""HTTP clients for VictoriaLogs and VictoriaTraces APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode


class VictoriaLogsClient:
    """Client for VictoriaLogs HTTP API (port 9428)."""

    def __init__(self, base_url: str) -> None:
        # Ensure base_url doesn't end with a slash
        self.base_url = base_url.rstrip("/")

    def _request(
        self, method: str, path: str, params: dict | None = None
    ) -> dict | str:
        """Make an HTTP request to VictoriaLogs."""
        url = f"{self.base_url}{path}"
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"

        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode("utf-8")
                # Try to parse as JSON
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"VictoriaLogs API error: HTTP {e.code} — {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach VictoriaLogs at {self.base_url}: {e.reason}"
            ) from e

    def query_logs(
        self,
        query: str,
        limit: int = 50,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Execute a LogsQL query and return matching log entries."""
        params = {"query": query, "limit": str(limit)}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        result = self._request("GET", "/select/logsql/query", params)
        # VictoriaLogs may return a stream of JSON lines or a JSON array
        if isinstance(result, str):
            # Parse stream of JSON lines
            entries = []
            for line in result.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        entries.append({"raw": line})
            return entries
        elif isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        return []

    def count_errors(self, service: str | None = None, window: str = "1h") -> dict:
        """Count errors in logs for a given service and time window."""
        query = f"_time:{window} severity:ERROR"
        if service:
            query = f'_time:{window} service.name:"{service}" severity:ERROR'

        entries = self.query_logs(query, limit=1000)
        return {
            "service": service or "all",
            "time_window": window,
            "error_count": len(entries),
            "sample_entries": entries[:5],
        }


class VictoriaTracesClient:
    """Client for VictoriaTraces HTTP API (port 10428, Jaeger-compatible)."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, params: dict | None = None) -> dict:
        """Make an HTTP request to VictoriaTraces Jaeger API."""
        url = f"{self.base_url}/select/jaeger/api{path}"
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"

        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"VictoriaTraces API error: HTTP {e.code} — {body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach VictoriaTraces at {self.base_url}: {e.reason}"
            ) from e

    def list_traces(self, service: str, limit: int = 20) -> list[dict]:
        """List recent traces for a service."""
        result = self._request("/traces", {"service": service, "limit": str(limit)})
        return result.get("data", [])

    def get_trace(self, trace_id: str) -> dict | None:
        """Fetch a specific trace by ID."""
        result = self._request(f"/traces/{trace_id}")
        traces = result.get("data", [])
        return traces[0] if traces else None
