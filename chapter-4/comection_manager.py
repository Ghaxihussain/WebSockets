from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        # Store connections by room_id -> list of (websocket, username)
        self.active_rooms: Dict[str, List[tuple]] = {}
    
    async def connect(self, websocket: WebSocket, room_id: str, username: str):
        await websocket.accept()
        
        # Create room if it doesn't exist
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []
        
        # Add user to room
        self.active_rooms[room_id].append((websocket, username))
        
        # Notify others in room
        await self.broadcast_to_room(
            room_id, 
            f"{username} has joined the chat",
            system=True
        )
    
    def disconnect(self, websocket: WebSocket, room_id: str, username: str):
        if room_id in self.active_rooms:
            self.active_rooms[room_id] = [
                (ws, user) for ws, user in self.active_rooms[room_id] 
                if ws != websocket
            ]
            
            # Clean up empty rooms
            if not self.active_rooms[room_id]:
                del self.active_rooms[room_id]
    
    async def broadcast_to_room(self, room_id: str, message: str, system: bool = False):
        if room_id in self.active_rooms:
            for websocket, username in self.active_rooms[room_id]:
                if system:
                    await websocket.send_json({
                        "type": "system",
                        "message": message
                    })
                else:
                    await websocket.send_text(message)
    
    async def send_personal_message(self, message: str, room_id: str, sender: str):
        if room_id in self.active_rooms:
            for websocket, username in self.active_rooms[room_id]:
                await websocket.send_json({
                    "type": "message",
                    "sender": sender,
                    "content": message
                })