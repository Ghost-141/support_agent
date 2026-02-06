import asyncio
import sys


def selector_loop_factory(use_subprocess: bool = False) -> asyncio.AbstractEventLoop:
    """
    Force a selector-based loop for psycopg async on Windows.
    Uvicorn 0.40 defaults to Proactor on Windows, which psycopg does not support.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()
