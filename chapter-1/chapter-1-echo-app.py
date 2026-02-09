
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Step 1: Accept the connection
    await websocket.accept()
    
    # Step 2: Keep listening for messages
    while True:
        # Receive a message from the client
        data = await websocket.receive_text()
        
        # Echo it back to the same client
        await websocket.send_text(f"Echo: {data}")



