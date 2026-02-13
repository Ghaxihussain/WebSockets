from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
import json

app = FastAPI()

active_connections = {}
offline_messages = {}
rooms = {}


@app.get("/")
async def get():
    with open("index.html") as f:
        return HTMLResponse(f.read())


@app.websocket("/ws/{room_id}/{username}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, username: str):
    await websocket.accept()

    # register user
    active_connections[username] = websocket

    # add to room
    if room_id not in rooms:
        rooms[room_id] = []
    if username not in rooms[room_id]:
        rooms[room_id].append(username)

    print(f"[CONNECT] {username} joined {room_id}")
    print(f"[QUEUE CHECK] offline_messages for {username}: {offline_messages.get(username, [])}")

    # send queued offline messages BEFORE anything else
    queued = offline_messages.pop(username, [])
    if queued:
        print(f"[SENDING UNREAD] {len(queued)} messages to {username}")
        await websocket.send_text(json.dumps({
            "type": "unread_batch",
            "messages": queued
        }))

    # notify other user that this user is online
    for user in rooms.get(room_id, []):
        if user != username and user in active_connections:
            try:
                await active_connections[user].send_text(json.dumps({
                    "type": "status",
                    "user": username,
                    "status": "online"
                }))
            except:
                pass

    try:
        while True:
            data = await websocket.receive_text()
            msg = {
                "sender": username,
                "content": data,
                "time": datetime.now().isoformat()
            }

            # find recipient
            recipient = None
            for user in rooms.get(room_id, []):
                if user != username:
                    recipient = user
                    break

            if recipient is None:
                print(f"[NO RECIPIENT] no other user in room {room_id}")
                continue

            if recipient in active_connections:
                try:
                    await active_connections[recipient].send_text(json.dumps({
                        "type": "message",
                        **msg
                    }))
                    print(f"[DELIVERED] {username} -> {recipient}: {data}")
                except:
                    # connection is stale, queue it
                    print(f"[STALE] {recipient} connection dead, queuing")
                    active_connections.pop(recipient, None)
                    offline_messages.setdefault(recipient, []).append(msg)
            else:
                # recipient offline, queue
                offline_messages.setdefault(recipient, []).append(msg)
                print(f"[QUEUED] {username} -> {recipient} (offline): {data}")

    except WebSocketDisconnect:
        active_connections.pop(username, None)
        print(f"[DISCONNECT] {username} left {room_id}")
        print(f"[STATE] active: {list(active_connections.keys())}")
        print(f"[STATE] offline_messages: {offline_messages}")

        for user in rooms.get(room_id, []):
            if user != username and user in active_connections:
                try:
                    await active_connections[user].send_text(json.dumps({
                        "type": "status",
                        "user": username,
                        "status": "offline"
                    }))
                except:
                    pass