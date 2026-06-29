"""Windows-compatible development server entry point.

Usage: python -m api.run

On Windows, use this instead of 'uvicorn api.main:app' — the default
ProactorEventLoop does not support psycopg async.  This script sets the
SelectorEventLoop policy before ANY asyncio-using module is imported.
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import uvicorn BEFORE api.main so uvicorn doesn't accidentally create
# a ProactorEventLoop before main.py's sync_engine is built.
import uvicorn

from api.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8401")),
        loop="asyncio",
    )
