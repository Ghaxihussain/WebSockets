# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .models import init_db
from .database import save_message, get_history
from .comection_manager import ConnectionManager
import json
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()       # create tables on startup
    yield                 # app runs
    # cleanup on shutdown (if needed)

app = FastAPI(lifespan=lifespan)
manager = ConnectionManager()


@app.websocket("/ws/{room_id}/{username}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, username: str):
    await manager.connect(websocket, room_id, username)

    # Send chat history to the user who just connected
    history = await get_history(room_id)
    for msg in history:
        await websocket.send_text(json.dumps({
            "sender": msg.sender,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "type": "history"
        }))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Save to database
            saved = await save_message(
                room_id=room_id,
                sender=username,
                content=message["content"]
            )

            # Broadcast to both users in the room
            outgoing = json.dumps({
                "sender": username,
                "content": message["content"],
                "timestamp": saved.timestamp.isoformat(),
                "type": "message"
            })
            await manager.broadcast_to_room(room_id, outgoing)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, username)