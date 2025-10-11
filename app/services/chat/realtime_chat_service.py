"""
Real-time chat service using WebSockets and Supabase real-time subscriptions
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from supabase import create_client, Client

from app.core.config import settings
from app.models.models import ChatMessageCreate, ChatMessageResponse, ChatMessageType, ChatMessageStatus
from app.services.chat.firebase_chat_service import firebase_chat_service
from app.services.notification.offline_alert_service import offline_alert_service

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time chat"""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, WebSocket] = {}
        # Store user subscriptions for Supabase real-time
        self.user_subscriptions: Dict[str, any] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a WebSocket connection and store it"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected to chat")
        
        # Subscribe to Supabase real-time updates for this user
        await self._subscribe_to_user_messages(user_id)
        
    def disconnect(self, user_id: str):
        """Remove a WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from chat")
            
        # Unsubscribe from Supabase real-time updates
        if user_id in self.user_subscriptions:
            # Note: Supabase Python client doesn't have direct unsubscribe method
            # The subscription will be cleaned up when the connection is closed
            del self.user_subscriptions[user_id]
    
    async def send_personal_message(self, message: str, user_id: str):
        """Send a message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast_message(self, message: str, exclude_user: Optional[str] = None):
        """Broadcast a message to all connected users except the excluded one"""
        disconnected_users = []
        
        for user_id, connection in self.active_connections.items():
            if exclude_user and user_id == exclude_user:
                continue
                
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    async def _subscribe_to_user_messages(self, user_id: str):
        """Subscribe to real-time updates for a user's messages"""
        try:
            # For now, we'll implement a simple polling mechanism
            # In a production environment, you might want to use:
            # 1. Supabase real-time with proper WebSocket connection
            # 2. Redis pub/sub
            # 3. Server-sent events
            # 4. WebSocket-based message broadcasting
            
            # Store the user subscription info
            self.user_subscriptions[user_id] = {
                "user_id": user_id,
                "subscribed_at": datetime.now(),
                "active": True
            }
            
            logger.info(f"Subscribed user {user_id} to real-time message updates (polling mode)")
            
        except Exception as e:
            logger.error(f"Error subscribing user {user_id} to real-time updates: {e}")

# Global connection manager instance
connection_manager = ConnectionManager()

class RealtimeChatService:
    """Real-time chat service that combines WebSockets with Supabase real-time"""
    
    def __init__(self):
        self.connection_manager = connection_manager
        
    async def handle_websocket_connection(self, websocket: WebSocket, user_id: str):
        """Handle a WebSocket connection for real-time chat"""
        await self.connection_manager.connect(websocket, user_id)
        
        try:
            while True:
                # Keep the connection alive and handle incoming messages
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle different message types
                if message_data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message_data.get("type") == "typing":
                    await self._handle_typing_indicator(message_data, user_id)
                elif message_data.get("type") == "message":
                    await self._handle_realtime_message(message_data, user_id)
                    
        except WebSocketDisconnect:
            self.connection_manager.disconnect(user_id)
        except Exception as e:
            logger.error(f"Error in WebSocket connection for user {user_id}: {e}")
            self.connection_manager.disconnect(user_id)
    
    async def _handle_typing_indicator(self, data: dict, user_id: str):
        """Handle typing indicator from a user"""
        recipient_id = data.get("recipient_id")
        is_typing = data.get("is_typing", False)
        
        if recipient_id:
            # Send typing indicator to recipient
            typing_message = json.dumps({
                "type": "typing",
                "sender_id": user_id,
                "is_typing": is_typing
            })
            await self.connection_manager.send_personal_message(typing_message, recipient_id)
    
    async def _handle_realtime_message(self, data: dict, user_id: str):
        """Handle a real-time message from a user"""
        try:
            # Create message object
            message_data = ChatMessageCreate(
                recipient_id=data.get("recipient_id"),
                message_type=ChatMessageType(data.get("message_type", "text")),
                content=data.get("content"),
                metadata=data.get("metadata", {})
            )
            
            # Send message using the existing chat service
            result = await firebase_chat_service.send_message(user_id, message_data)
            
            # Send confirmation back to sender
            confirmation = json.dumps({
                "type": "message_sent",
                "message_id": result.id,
                "status": "success"
            })
            await self.connection_manager.send_personal_message(confirmation, user_id)
            
            # Send the message to recipient via WebSocket
            message_json = json.dumps({
                "type": "new_message",
                "data": {
                    "id": result.id,
                    "sender_id": result.sender_id,
                    "recipient_id": result.recipient_id,
                    "message_type": result.message_type.value,
                    "content": result.content,
                    "status": result.status.value,
                    "metadata": result.metadata,
                    "created_at": result.created_at.isoformat(),
                    "sender_name": result.sender_name,
                    "sender_email": result.sender_email
                }
            })
            await self.connection_manager.send_personal_message(message_json, result.recipient_id)
            
        except Exception as e:
            logger.error(f"Error handling real-time message: {e}")
            error_message = json.dumps({
                "type": "error",
                "message": "Failed to send message"
            })
            await self.connection_manager.send_personal_message(error_message, user_id)
    
    async def notify_message_sent(self, message: ChatMessageResponse):
        """Notify users when a message is sent (called by the regular chat service)"""
        # Send to recipient via WebSocket
        message_json = json.dumps({
            "type": "new_message",
            "data": {
                "id": message.id,
                "sender_id": message.sender_id,
                "recipient_id": message.recipient_id,
                "message_type": message.message_type.value,
                "content": message.content,
                "status": message.status.value,
                "metadata": message.metadata,
                "created_at": message.created_at.isoformat(),
                "sender_name": message.sender_name,
                "sender_email": message.sender_email
            }
        })
        
        # Send to recipient
        delivered = await self.connection_manager.send_personal_message(message_json, message.recipient_id)
        
        # Send confirmation to sender
        confirmation = json.dumps({
            "type": "message_delivered",
            "message_id": message.id,
            "recipient_id": message.recipient_id
        })
        await self.connection_manager.send_personal_message(confirmation, message.sender_id)

        # If recipient not connected, trigger offline alerts (WhatsApp + Email)
        try:
            is_online = self.is_user_online(message.recipient_id)
            logger.info(
                f"Post-send status for recipient {message.recipient_id}: online={is_online}, delivered={delivered}"
            )
            await offline_alert_service.maybe_notify_offline_recipient(message, is_online)
        except Exception as e:
            logger.warning(f"Failed to trigger offline alerts: {e}")
    
    async def notify_message_read(self, message_id: str, reader_id: str, sender_id: str):
        """Notify sender when their message is read"""
        read_notification = json.dumps({
            "type": "message_read",
            "message_id": message_id,
            "reader_id": reader_id
        })
        await self.connection_manager.send_personal_message(read_notification, sender_id)
    
    def get_connected_users(self) -> List[str]:
        """Get list of currently connected user IDs"""
        return list(self.connection_manager.active_connections.keys())
    
    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is currently online"""
        return user_id in self.connection_manager.active_connections

# Global real-time chat service instance
realtime_chat_service = RealtimeChatService()
