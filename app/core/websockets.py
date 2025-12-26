from typing import List, Dict
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # active_connections: Dict[user_id, List[WebSocket]]
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected")

    async def send_personal_message(self, message: dict, user_id: str):
        """Send a message to a specific user's active connections."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to {user_id}: {e}")
                    # Clean up dead connection might be needed here

    async def broadcast(self, message: dict):
        """Broadcast message to all connected users (use carefully)."""
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                await connection.send_json(message)

manager = ConnectionManager()
