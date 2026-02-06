from fastapi import Request, WebSocket
from psycopg_pool import AsyncConnectionPool


def get_db_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.db_pool


def get_db_pool_ws(websocket: WebSocket) -> AsyncConnectionPool:
    return websocket.app.state.db_pool
