

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
import json

app = FastAPI()


class PresenceManager:
    def __init__(self):
        # user_id -> WebSocket connection
        self.active_connections: dict[str, WebSocket] = {}
        # user_id -> last seen timestamp (for offline users)
        self.last_seen: dict[str, datetime] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # Send the NEW user a list of who's already online
        online_users = [
            uid for uid in self.active_connections if uid != user_id
        ]
        await websocket.send_json({
            "type": "user_list",
            "online_users": online_users,
            "last_seen": {
                uid: ts.isoformat()
                for uid, ts in self.last_seen.items()
                if uid != user_id
            },
        })

        # Notify ALL OTHER users that this user came online
        await self.broadcast_status(user_id, "online")

    async def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            self.last_seen[user_id] = datetime.now()
            await self.broadcast_status(user_id, "offline")

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_connections

    async def broadcast_status(self, user_id: str, status: str):
        """Tell all OTHER connected users about this user's status change."""
        message = {
            "type": "presence",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        if status == "offline" and user_id in self.last_seen:
            message["last_seen"] = self.last_seen[user_id].isoformat()

        for uid, ws in self.active_connections.items():
            if uid != user_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass  # Handle broken connections gracefully

    async def send_to_user(self, target_user_id: str, message: dict):
        """Send a message to a specific user if they're online."""
        if target_user_id in self.active_connections:
            await self.active_connections[target_user_id].send_json(message)
            return True
        return False


manager = PresenceManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # Reject if user_id is already connected
    if user_id in manager.active_connections:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": f"User '{user_id}' is already connected in another tab."
        })
        await websocket.close()
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                # Route chat message to the target user
                target = data.get("to")
                chat_message = {
                    "type": "chat",
                    "from": user_id,
                    "message": data.get("message", ""),
                    "timestamp": datetime.now().isoformat(),
                }
                delivered = await manager.send_to_user(target, chat_message)

                # Send delivery status back to sender
                await websocket.send_json({
                    "type": "delivery_status",
                    "to": target,
                    "delivered": delivered,
                    "timestamp": chat_message["timestamp"],
                })

    except WebSocketDisconnect:
        await manager.disconnect(user_id)
    except Exception as e:
        print(f"Error for {user_id}: {e}")
        await manager.disconnect(user_id)