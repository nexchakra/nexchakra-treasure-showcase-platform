import asyncio
import websockets
import json

async def mock_client():
    uri = "ws://localhost:8000/ws/notifications"
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Successfully connected to NexChakra WebSocket!")
            print("⏳ Waiting for backend events (Try placing an order in Postman/Docs)...")
            
            while True:
                # This stays open and prints any message the server sends
                message = await websocket.recv()
                data = json.loads(message)
                print(f"🔔 NEW EVENT RECEIVED: {data}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(mock_client())