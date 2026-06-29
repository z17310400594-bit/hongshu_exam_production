"""ASGI entry point — sets Windows-compatible event loop BEFORE app import.

Usage: uvicorn api.asgi:app
Not:  uvicorn api.main:app  (main.py is imported directly, skipping this file)
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api.main import app  # noqa: E402

__all__ = ["app"]
