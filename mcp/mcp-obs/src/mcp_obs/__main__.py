"""Allow running as `python -m mcp_obs [logs_url] [traces_url]`."""

import asyncio
import sys

from mcp_obs.server import main

if __name__ == "__main__":
    logs_url = sys.argv[1] if len(sys.argv) > 1 else None
    traces_url = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(main(logs_url, traces_url))
