from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from api.services.websocket import manager
from agent import run_agent
from api.dependency import get_db_pool_ws
from psycopg_pool import AsyncConnectionPool
import json
import os

ws_router = APIRouter()
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "1000"))


@ws_router.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    pool: AsyncConnectionPool = Depends(get_db_pool_ws),
):
    await manager.connect(websocket)
    try:
        while True:
            # Expecting message as a string or JSON
            data = await websocket.receive_text()

            # Simple check if data is JSON
            try:
                message_data = json.loads(data)
                user_message = message_data.get("text", data)
            except json.JSONDecodeError:
                user_message = data

            if user_message and len(user_message) > MAX_MESSAGE_LENGTH:
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "error",
                            "text": "Your message is too long. Please try again with a shorter message.",
                        }
                    ),
                    websocket,
                )
                continue

            # Use client_id as the unique identifier for the thread
            # and "websocket" as the channel
            response = await run_agent(
                user_message, client_id, pool, channel="websocket"
            )
            await manager.send_personal_message(
                json.dumps({"type": "message", "text": response}), websocket
            )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client #{client_id} left the chat")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
