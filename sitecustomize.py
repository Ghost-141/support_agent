import asyncio
import sys


# Ensure selector-based event loop on Windows before anything creates a loop.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
