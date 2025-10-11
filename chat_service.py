"""
Chat Service for handling message storage and retrieval
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from app.core.database import get_supabase
from app.models import (
    ChatMessageCreate, 
    ChatMessageResponse, 
    ChatConversationResponse,
    ChatMessageStatus,
    ChatMessageType
)

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        self.supabase = get_supabase()
    
    async def send_message(self, sender_id: str, message_data: ChatMessageCreate) -> ChatMessageResponse:
        """Send a new chat message"""
        try:
            # Create message record
            message_id = str(uuid.uuid4())
            message_record = {
                "id": message_id,
                "sender_id": sender_id,
                "recipient_id": message_data.recipient_id,
                "message_type": message_data.message_type.value,
                "content": message_data.content,
                "status": ChatMessageStatus.SENT.value,
                "metadata": message_data.metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert message into database
            result = self.supabase.table("chat_messages").insert(message_record).execute()
            
            if result.data:
                # Get sender and recipient details
                sender_details = await self._get_user_details(sender_id)
                recipient_details = await self._get_user_details(message_data.recipient_id)
                
                # Create response
                response = ChatMessageResponse(
                    id=message_id,
                    sender_id=sender_id,
                    recipient_id=message_data.recipient_id,
                    message_type=message_data.message_type,
                    content=message_data.content,
                    status=ChatMessageStatus.SENT,
                    metadata=message_data.metadata,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    sender_name=sender_details.get("full_name") if sender_details else None,
                    sender_email=sender_details.get("email") if sender_details else None,
                    recipient_name=recipient_details.get("full_name") if recipient_details else None,
                    recipient_email=recipient_details.get("email") if recipient_details else None
                )
                
                return response
            else:
                raise Exception("Failed to insert message into database")
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def get_conversation_messages(
        self, 
        user_id: str, 
        other_user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ChatMessageResponse]:
        """Get messages between two users"""
        try:
            # Get messages where user is either sender or recipient
            # First get messages where user is sender
            result1 = self.supabase.table("chat_messages").select(
                "*, sender:users!sender_id(*), recipient:users!recipient_id(*)"
            ).eq("sender_id", user_id).eq("recipient_id", other_user_id).execute()
            
            # Then get messages where user is recipient
            result2 = self.supabase.table("chat_messages").select(
                "*, sender:users!sender_id(*), recipient:users!recipient_id(*)"
            ).eq("sender_id", other_user_id).eq("recipient_id", user_id).execute()
            
            # Combine results
            all_messages = result1.data + result2.data
            
            # Sort by created_at and apply limit/offset
            all_messages.sort(key=lambda x: x["created_at"], reverse=True)
            all_messages = all_messages[offset:offset + limit]
            
            messages = []
            for msg in all_messages:
                message = ChatMessageResponse(
                    id=msg["id"],
                    sender_id=msg["sender_id"],
                    recipient_id=msg["recipient_id"],
                    message_type=ChatMessageType(msg["message_type"]),
                    content=msg["content"],
                    status=ChatMessageStatus(msg["status"]),
                    metadata=msg.get("metadata", {}),
                    created_at=datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(msg["updated_at"].replace('Z', '+00:00')),
                    sender_name=msg.get("sender", {}).get("full_name"),
                    sender_email=msg.get("sender", {}).get("email"),
                    recipient_name=msg.get("recipient", {}).get("full_name"),
                    recipient_email=msg.get("recipient", {}).get("email")
                )
                messages.append(message)
            
            # Return messages in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Error getting conversation messages: {e}")
            raise
    
    async def get_user_conversations(self, user_id: str) -> List[ChatConversationResponse]:
        """Get all conversations for a user"""
        try:
            # Get distinct conversations (other users) for this user
            # Get messages where user is sender
            result1 = self.supabase.table("chat_messages").select(
                "*, sender:users!sender_id(*), recipient:users!recipient_id(*)"
            ).eq("sender_id", user_id).order("created_at", desc=True).execute()
            
            # Get messages where user is recipient
            result2 = self.supabase.table("chat_messages").select(
                "*, sender:users!sender_id(*), recipient:users!recipient_id(*)"
            ).eq("recipient_id", user_id).order("created_at", desc=True).execute()
            
            # Combine results
            all_messages = result1.data + result2.data
            
            # Group messages by conversation partner
            conversations = {}
            for msg in all_messages:
                # Determine the other user in the conversation
                if msg["sender_id"] == user_id:
                    other_user_id = msg["recipient_id"]
                    other_user = msg.get("recipient", {})
                else:
                    other_user_id = msg["sender_id"]
                    other_user = msg.get("sender", {})
                
                # Create conversation if it doesn't exist
                if other_user_id not in conversations:
                    conversations[other_user_id] = {
                        "conversation_id": other_user_id,  # Using user_id as conversation_id
                        "participant_id": other_user_id,
                        "participant_name": other_user.get("full_name", "Unknown"),
                        "participant_email": other_user.get("email", ""),
                        "last_message": None,
                        "unread_count": 0,
                        "last_activity": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                        "created_at": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                    }
                
                # Update with latest message if this is more recent
                msg_time = datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                if msg_time > conversations[other_user_id]["last_activity"]:
                    conversations[other_user_id]["last_activity"] = msg_time
                    conversations[other_user_id]["last_message"] = ChatMessageResponse(
                        id=msg["id"],
                        sender_id=msg["sender_id"],
                        recipient_id=msg["recipient_id"],
                        message_type=ChatMessageType(msg["message_type"]),
                        content=msg["content"],
                        status=ChatMessageStatus(msg["status"]),
                        metadata=msg.get("metadata", {}),
                        created_at=msg_time,
                        updated_at=datetime.fromisoformat(msg["updated_at"].replace('Z', '+00:00')),
                        sender_name=msg.get("sender", {}).get("full_name"),
                        sender_email=msg.get("sender", {}).get("email"),
                        recipient_name=msg.get("recipient", {}).get("full_name"),
                        recipient_email=msg.get("recipient", {}).get("email")
                    )
                
                # Count unread messages (messages sent to this user that are not read)
                if msg["recipient_id"] == user_id and msg["status"] != ChatMessageStatus.READ.value:
                    conversations[other_user_id]["unread_count"] += 1
            
            # Convert to list and sort by last activity
            conversation_list = list(conversations.values())
            conversation_list.sort(key=lambda x: x["last_activity"], reverse=True)
            
            return [ChatConversationResponse(**conv) for conv in conversation_list]
            
        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            raise
    
    async def mark_messages_as_read(self, user_id: str, sender_id: str) -> bool:
        """Mark messages from a specific sender as read"""
        try:
            result = self.supabase.table("chat_messages").update({
                "status": ChatMessageStatus.READ.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("sender_id", sender_id).eq("recipient_id", user_id).eq("status", ChatMessageStatus.SENT.value).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error marking messages as read: {e}")
            return False
    
    async def mark_message_as_delivered(self, message_id: str) -> bool:
        """Mark a specific message as delivered"""
        try:
            result = self.supabase.table("chat_messages").update({
                "status": ChatMessageStatus.DELIVERED.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", message_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error marking message as delivered: {e}")
            return False
    
    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Delete a message (soft delete by updating content)"""
        try:
            # Check if user is the sender
            result = self.supabase.table("chat_messages").select("sender_id").eq("id", message_id).execute()
            
            if result.data and result.data[0]["sender_id"] == user_id:
                # Soft delete by updating content
                self.supabase.table("chat_messages").update({
                    "content": "[Message deleted]",
                    "metadata": {"deleted": True, "deleted_at": datetime.utcnow().isoformat()},
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", message_id).execute()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return False
    
    async def _get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details by user_id"""
        try:
            result = self.supabase.table("users").select("full_name, email").eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None

# Service instance
chat_service = ChatService()
