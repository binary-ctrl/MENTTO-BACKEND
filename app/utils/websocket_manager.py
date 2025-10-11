"""
WebSocket Connection Manager for real-time chat
"""

import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store active connections: {user_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Store user sessions: {user_id: {"websocket": WebSocket, "last_seen": datetime}}
        self.user_sessions: Dict[str, Dict] = {}
        # Store typing indicators: {user_id: {"typing_to": recipient_id, "timestamp": datetime}}
        self.typing_indicators: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = {
            "websocket": websocket,
            "last_seen": datetime.utcnow(),
            "status": "online"
        }
        logger.info(f"User {user_id} connected to WebSocket")
        
        # Notify other users that this user is online
        await self.broadcast_user_status(user_id, "online")

    def disconnect(self, user_id: str):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        if user_id in self.typing_indicators:
            del self.typing_indicators[user_id]
        logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: str, user_id: str):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False

    async def send_json_message(self, data: dict, user_id: str):
        """Send a JSON message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(data)
                return True
            except Exception as e:
                logger.error(f"Error sending JSON to {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False

    async def broadcast_to_conversation(self, message: dict, sender_id: str, recipient_id: str):
        """Send a message to both participants in a conversation"""
        # Send to recipient
        if recipient_id in self.active_connections:
            await self.send_json_message(message, recipient_id)
        
        # Send confirmation to sender
        if sender_id in self.active_connections:
            confirmation = {
                **message,
                "status": "delivered",
                "delivered_at": datetime.utcnow().isoformat()
            }
            await self.send_json_message(confirmation, sender_id)

    async def send_typing_indicator(self, sender_id: str, recipient_id: str, is_typing: bool):
        """Send typing indicator to recipient"""
        if recipient_id in self.active_connections:
            typing_message = {
                "type": "typing",
                "data": {
                    "sender_id": sender_id,
                    "is_typing": is_typing,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            await self.send_json_message(typing_message, recipient_id)

    async def send_read_receipt(self, sender_id: str, recipient_id: str, message_id: str):
        """Send read receipt to sender"""
        if sender_id in self.active_connections:
            read_receipt = {
                "type": "read_receipt",
                "data": {
                    "message_id": message_id,
                    "read_by": recipient_id,
                    "read_at": datetime.utcnow().isoformat()
                }
            }
            await self.send_json_message(read_receipt, sender_id)

    async def broadcast_user_status(self, user_id: str, status: str):
        """Broadcast user online/offline status to all connected users"""
        status_message = {
            "type": "user_status",
            "data": {
                "user_id": user_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Send to all connected users except the user themselves
        for connected_user_id in list(self.active_connections.keys()):
            if connected_user_id != user_id:
                await self.send_json_message(status_message, connected_user_id)

    async def send_message_notification(self, recipient_id: str, sender_name: str, message_preview: str):
        """Send a notification about a new message"""
        if recipient_id in self.active_connections:
            notification = {
                "type": "message_notification",
                "data": {
                    "sender_name": sender_name,
                    "message_preview": message_preview,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            await self.send_json_message(notification, recipient_id)

    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is currently online"""
        return user_id in self.active_connections

    def get_online_users(self) -> List[str]:
        """Get list of currently online user IDs"""
        return list(self.active_connections.keys())

    def get_user_count(self) -> int:
        """Get total number of connected users"""
        return len(self.active_connections)

    async def cleanup_inactive_connections(self):
        """Clean up inactive connections (called periodically)"""
        current_time = datetime.utcnow()
        inactive_users = []
        
        for user_id, session in self.user_sessions.items():
            # Consider user inactive if last seen > 5 minutes ago
            if (current_time - session["last_seen"]).seconds > 300:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            logger.info(f"Cleaning up inactive connection for user {user_id}")
            self.disconnect(user_id)
            await self.broadcast_user_status(user_id, "offline")

    def update_user_activity(self, user_id: str):
        """Update user's last seen timestamp"""
        if user_id in self.user_sessions:
            self.user_sessions[user_id]["last_seen"] = datetime.utcnow()

    async def handle_websocket_message(self, websocket: WebSocket, user_id: str, message: dict):
        """Handle incoming WebSocket messages"""
        try:
            message_type = message.get("type")
            data = message.get("data", {})
            
            if message_type == "ping":
                # Respond to ping with pong
                await self.send_json_message({
                    "type": "pong",
                    "data": {"timestamp": datetime.utcnow().isoformat()}
                }, user_id)
                self.update_user_activity(user_id)
                
            elif message_type == "typing":
                recipient_id = data.get("recipient_id")
                is_typing = data.get("is_typing", False)
                if recipient_id:
                    await self.send_typing_indicator(user_id, recipient_id, is_typing)
                    
            elif message_type == "read":
                message_id = data.get("message_id")
                sender_id = data.get("sender_id")
                if message_id and sender_id:
                    await self.send_read_receipt(sender_id, user_id, message_id)
                    
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

# Global connection manager instance
manager = ConnectionManager()
