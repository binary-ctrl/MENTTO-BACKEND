"""
Firebase Chat Service for 1:1 messaging
Uses Firebase Realtime Database for real-time chat functionality
"""

import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import firebase_admin
from firebase_admin import credentials, db
from app.core.config import settings
from app.core.database import get_supabase
from app.models.models import (
    ChatMessageCreate, 
    ChatMessageResponse, 
    ChatConversationResponse,
    ChatMessageStatus,
    ChatMessageType
)

logger = logging.getLogger(__name__)

class FirebaseChatService:
    def __init__(self):
        self.supabase = get_supabase()
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase configuration is available
            if not settings.firebase_project_id:
                logger.warning("Firebase project ID not configured. Chat service will use Supabase only.")
                self.db_ref = None
                return
            
            if not firebase_admin._apps:
                # Initialize Firebase with service account credentials
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": settings.firebase_project_id,
                    "private_key_id": settings.firebase_private_key_id,
                    "private_key": settings.firebase_private_key.replace('\\n', '\n') if settings.firebase_private_key else None,
                    "client_email": settings.firebase_client_email,
                    "client_id": settings.firebase_client_id,
                    "auth_uri": settings.firebase_auth_uri,
                    "token_uri": settings.firebase_token_uri,
                })
                
                # Construct database URL
                database_url = f'https://{settings.firebase_project_id}-default-rtdb.firebaseio.com/'
                
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url
                })
            
            self.db_ref = db.reference('/')
            logger.info("Firebase initialized successfully for chat service")
            
        except Exception as e:
            logger.warning(f"Failed to initialize Firebase: {e}. Chat service will use Supabase only.")
            self.db_ref = None
    
    async def send_message(self, sender_id: str, message_data: ChatMessageCreate) -> ChatMessageResponse:
        """Send a new chat message using Firebase"""
        try:
            # Create message record
            message_id = str(uuid.uuid4())
            timestamp = datetime.utcnow()
            
            # Get sender and recipient details
            sender_details = await self._get_user_details(sender_id)
            recipient_details = await self._get_user_details(message_data.recipient_id)
            
            # Create message object (only include columns that exist in the database)
            message_obj = {
                "id": message_id,
                "sender_id": sender_id,
                "recipient_id": message_data.recipient_id,
                "message_type": message_data.message_type.value,
                "content": message_data.content,
                "status": ChatMessageStatus.SENT.value,
                "metadata": message_data.metadata or {},
                "created_at": timestamp.isoformat(),
                "updated_at": timestamp.isoformat()
            }
            
            # Store in Supabase for persistence
            await self._store_message_in_supabase(message_obj)
            
            # Store in Firebase for real-time updates (with additional user details)
            firebase_message_obj = {
                **message_obj,
                "sender_name": sender_details.get("full_name") if sender_details else None,
                "sender_email": sender_details.get("email") if sender_details else None,
                "recipient_name": recipient_details.get("full_name") if recipient_details else None,
                "recipient_email": recipient_details.get("email") if recipient_details else None
            }
            await self._store_message_in_firebase(firebase_message_obj)
            
            # Create response
            response = ChatMessageResponse(
                id=message_id,
                sender_id=sender_id,
                recipient_id=message_data.recipient_id,
                message_type=message_data.message_type,
                content=message_data.content,
                status=ChatMessageStatus.SENT,
                metadata=message_data.metadata,
                created_at=timestamp,
                updated_at=timestamp,
                sender_name=sender_details.get("full_name") if sender_details else None,
                sender_email=sender_details.get("email") if sender_details else None,
                recipient_name=recipient_details.get("full_name") if recipient_details else None,
                recipient_email=recipient_details.get("email") if recipient_details else None
            )
            
            # Notify real-time service about the new message
            try:
                from app.services.chat.realtime_chat_service import realtime_chat_service
                await realtime_chat_service.notify_message_sent(response)
            except Exception as e:
                logger.warning(f"Failed to notify real-time service: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def _store_message_in_supabase(self, message_obj: dict):
        """Store message in Supabase for persistence"""
        try:
            result = self.supabase.table("chat_messages").insert(message_obj).execute()
            if not result.data:
                raise Exception("Failed to insert message into Supabase")
        except Exception as e:
            logger.error(f"Error storing message in Supabase: {e}")
            raise
    
    async def _store_message_in_firebase(self, message_obj: dict):
        """Store message in Firebase for real-time updates"""
        if not self.db_ref:
            logger.info("Firebase not available, skipping Firebase storage")
            return
            
        try:
            # Create conversation path
            conversation_id = self._get_conversation_id(message_obj["sender_id"], message_obj["recipient_id"])
            
            # Store message in Firebase
            messages_ref = self.db_ref.child('conversations').child(conversation_id).child('messages').child(message_obj["id"])
            messages_ref.set(message_obj)
            
            # Update conversation metadata
            conversation_ref = self.db_ref.child('conversations').child(conversation_id)
            conversation_ref.update({
                'last_message': message_obj,
                'last_activity': message_obj["created_at"],
                'updated_at': datetime.utcnow().isoformat()
            })
            
            # Update user's conversation list
            self._update_user_conversations(message_obj["sender_id"], conversation_id, message_obj)
            self._update_user_conversations(message_obj["recipient_id"], conversation_id, message_obj)
            
        except Exception as e:
            logger.error(f"Error storing message in Firebase: {e}")
            # Don't raise, just log the error and continue with Supabase
    
    def _get_conversation_id(self, user1_id: str, user2_id: str) -> str:
        """Generate a consistent conversation ID for two users"""
        # Sort user IDs to ensure consistent conversation ID
        sorted_ids = sorted([user1_id, user2_id])
        return f"{sorted_ids[0]}_{sorted_ids[1]}"
    
    def _update_user_conversations(self, user_id: str, conversation_id: str, message_obj: dict):
        """Update user's conversation list in Firebase"""
        if not self.db_ref:
            return
            
        try:
            user_conversations_ref = self.db_ref.child('user_conversations').child(user_id).child(conversation_id)
            user_conversations_ref.update({
                'conversation_id': conversation_id,
                'last_message': message_obj,
                'last_activity': message_obj["created_at"],
                'unread_count': 0 if message_obj["sender_id"] == user_id else 1,
                'updated_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error updating user conversations: {e}")
    
    async def get_conversation_messages(
        self, 
        user_id: str, 
        other_user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ChatMessageResponse]:
        """Get messages between two users from Firebase"""
        if not self.db_ref:
            # Firebase not available, use Supabase
            return await self._get_conversation_messages_from_supabase(user_id, other_user_id, limit, offset)
            
        try:
            conversation_id = self._get_conversation_id(user_id, other_user_id)
            messages_ref = self.db_ref.child('conversations').child(conversation_id).child('messages')
            
            # Get messages from Firebase
            messages_snapshot = messages_ref.order_by_child('created_at').get()
            
            if not messages_snapshot:
                return []
            
            # Convert to list and sort
            messages = []
            for message_id, message_data in messages_snapshot.items():
                if message_data:
                    message = ChatMessageResponse(
                        id=message_data["id"],
                        sender_id=message_data["sender_id"],
                        recipient_id=message_data["recipient_id"],
                        message_type=ChatMessageType(message_data["message_type"]),
                        content=message_data["content"],
                        status=ChatMessageStatus(message_data["status"]),
                        metadata=message_data.get("metadata", {}),
                        created_at=datetime.fromisoformat(message_data["created_at"]),
                        updated_at=datetime.fromisoformat(message_data["updated_at"]),
                        sender_name=message_data.get("sender_name"),
                        sender_email=message_data.get("sender_email"),
                        recipient_name=message_data.get("recipient_name"),
                        recipient_email=message_data.get("recipient_email")
                    )
                    messages.append(message)
            
            # Sort by created_at (oldest first)
            messages.sort(key=lambda x: x.created_at)
            
            # Apply offset and limit
            return messages[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error getting conversation messages from Firebase: {e}")
            # Fallback to Supabase if Firebase fails
            return await self._get_conversation_messages_from_supabase(user_id, other_user_id, limit, offset)
    
    async def _get_conversation_messages_from_supabase(
        self, 
        user_id: str, 
        other_user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[ChatMessageResponse]:
        """Fallback method to get messages from Supabase"""
        try:
            # Get messages where user is either sender or recipient
            result1 = self.supabase.table("chat_messages").select("*").eq("sender_id", user_id).eq("recipient_id", other_user_id).execute()
            result2 = self.supabase.table("chat_messages").select("*").eq("sender_id", other_user_id).eq("recipient_id", user_id).execute()
            
            # Combine results
            all_messages = result1.data + result2.data
            
            # Sort by created_at and apply limit/offset
            all_messages.sort(key=lambda x: x["created_at"], reverse=True)
            all_messages = all_messages[offset:offset + limit]
            
            messages = []
            for msg in all_messages:
                # Get user details for sender and recipient
                sender_details = await self._get_user_details(msg["sender_id"])
                recipient_details = await self._get_user_details(msg["recipient_id"])
                
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
                    sender_name=sender_details.get("full_name") if sender_details else None,
                    sender_email=sender_details.get("email") if sender_details else None,
                    recipient_name=recipient_details.get("full_name") if recipient_details else None,
                    recipient_email=recipient_details.get("email") if recipient_details else None
                )
                messages.append(message)
            
            # Return messages in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Error getting conversation messages from Supabase: {e}")
            return []
    
    async def get_user_conversations(self, user_id: str) -> List[ChatConversationResponse]:
        """Get all conversations for a user from Firebase"""
        if not self.db_ref:
            # Firebase not available, use Supabase
            return await self._get_user_conversations_from_supabase(user_id)
            
        try:
            user_conversations_ref = self.db_ref.child('user_conversations').child(user_id)
            conversations_snapshot = user_conversations_ref.order_by_child('last_activity').get()
            
            if not conversations_snapshot:
                return []
            
            conversations = []
            for conversation_id, conv_data in conversations_snapshot.items():
                if conv_data:
                    # Get participant details
                    other_user_id = self._get_other_user_id(conversation_id, user_id)
                    participant_details = await self._get_user_details(other_user_id)
                    
                    conversation = ChatConversationResponse(
                        conversation_id=conversation_id,
                        participant_id=other_user_id,
                        participant_name=participant_details.get("full_name", "Unknown") if participant_details else "Unknown",
                        participant_email=participant_details.get("email", "") if participant_details else "",
                        last_message=ChatMessageResponse(**conv_data["last_message"]) if conv_data.get("last_message") else None,
                        unread_count=conv_data.get("unread_count", 0),
                        last_activity=datetime.fromisoformat(conv_data["last_activity"]),
                        created_at=datetime.fromisoformat(conv_data.get("created_at", conv_data["last_activity"]))
                    )
                    conversations.append(conversation)
            
            # Sort by last activity (most recent first)
            conversations.sort(key=lambda x: x.last_activity, reverse=True)
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting user conversations from Firebase: {e}")
            # Fallback to Supabase
            return await self._get_user_conversations_from_supabase(user_id)
    
    def _get_other_user_id(self, conversation_id: str, user_id: str) -> str:
        """Get the other user ID from conversation ID"""
        user_ids = conversation_id.split('_')
        return user_ids[1] if user_ids[0] == user_id else user_ids[0]
    
    async def _get_user_conversations_from_supabase(self, user_id: str) -> List[ChatConversationResponse]:
        """Fallback method to get conversations from Supabase"""
        try:
            # Get messages where user is sender
            result1 = self.supabase.table("chat_messages").select("*").eq("sender_id", user_id).order("created_at", desc=True).execute()
            
            # Get messages where user is recipient
            result2 = self.supabase.table("chat_messages").select("*").eq("recipient_id", user_id).order("created_at", desc=True).execute()
            
            # Combine results
            all_messages = result1.data + result2.data
            
            # Group messages by conversation partner
            conversations = {}
            for msg in all_messages:
                # Determine the other user in the conversation
                if msg["sender_id"] == user_id:
                    other_user_id = msg["recipient_id"]
                else:
                    other_user_id = msg["sender_id"]
                
                # Create conversation if it doesn't exist
                if other_user_id not in conversations:
                    conversations[other_user_id] = {
                        "conversation_id": other_user_id,
                        "participant_id": other_user_id,
                        "participant_name": msg.get("recipient_name") if msg["sender_id"] == user_id else msg.get("sender_name"),
                        "participant_email": msg.get("recipient_email") if msg["sender_id"] == user_id else msg.get("sender_email"),
                        "last_message": None,
                        "unread_count": 0,
                        "last_activity": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                        "created_at": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                    }
                
                # Update with latest message if this is more recent
                msg_time = datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                if msg_time > conversations[other_user_id]["last_activity"]:
                    conversations[other_user_id]["last_activity"] = msg_time
                    
                    # Get user details for the message
                    sender_details = await self._get_user_details(msg["sender_id"])
                    recipient_details = await self._get_user_details(msg["recipient_id"])
                    
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
                        sender_name=sender_details.get("full_name") if sender_details else None,
                        sender_email=sender_details.get("email") if sender_details else None,
                        recipient_name=recipient_details.get("full_name") if recipient_details else None,
                        recipient_email=recipient_details.get("email") if recipient_details else None
                    )
                
                # Count unread messages
                if msg["recipient_id"] == user_id and msg["status"] != ChatMessageStatus.READ.value:
                    conversations[other_user_id]["unread_count"] += 1
            
            # Convert to list and sort by last activity
            conversation_list = list(conversations.values())
            conversation_list.sort(key=lambda x: x["last_activity"], reverse=True)
            
            return [ChatConversationResponse(**conv) for conv in conversation_list]
            
        except Exception as e:
            logger.error(f"Error getting user conversations from Supabase: {e}")
            return []
    
    async def mark_messages_as_read(self, user_id: str, sender_id: str) -> bool:
        """Mark messages from a specific sender as read"""
        try:
            # Update in Supabase
            result = self.supabase.table("chat_messages").update({
                "status": ChatMessageStatus.READ.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("sender_id", sender_id).eq("recipient_id", user_id).eq("status", ChatMessageStatus.SENT.value).execute()
            
            # Update in Firebase if available
            if self.db_ref:
                conversation_id = self._get_conversation_id(user_id, sender_id)
                messages_ref = self.db_ref.child('conversations').child(conversation_id).child('messages')
                messages_snapshot = messages_ref.order_by_child('sender_id').equal_to(sender_id).get()
                
                for message_id, message_data in messages_snapshot.items():
                    if message_data and message_data.get("recipient_id") == user_id and message_data.get("status") == ChatMessageStatus.SENT.value:
                        messages_ref.child(message_id).update({
                            "status": ChatMessageStatus.READ.value,
                            "updated_at": datetime.utcnow().isoformat()
                        })
                
                # Update unread count
                user_conversations_ref = self.db_ref.child('user_conversations').child(user_id).child(conversation_id)
                user_conversations_ref.update({
                    "unread_count": 0,
                    "updated_at": datetime.utcnow().isoformat()
                })
            
            # Notify real-time service about read messages
            if len(result.data) > 0:
                try:
                    from app.services.chat.realtime_chat_service import realtime_chat_service
                    for message in result.data:
                        await realtime_chat_service.notify_message_read(
                            message["id"], 
                            user_id, 
                            message["sender_id"]
                        )
                except Exception as e:
                    logger.warning(f"Failed to notify real-time service about read messages: {e}")
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error marking messages as read: {e}")
            return False
    
    async def mark_message_as_delivered(self, message_id: str) -> bool:
        """Mark a specific message as delivered"""
        try:
            # Update in Supabase
            result = self.supabase.table("chat_messages").update({
                "status": ChatMessageStatus.DELIVERED.value,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", message_id).execute()
            
            # Update in Firebase if available
            if self.db_ref:
                # Find the message in Firebase and update it
                conversations_ref = self.db_ref.child('conversations')
                conversations_snapshot = conversations_ref.get()
                
                for conversation_id, conv_data in conversations_snapshot.items():
                    if conv_data and 'messages' in conv_data:
                        messages = conv_data['messages']
                        if message_id in messages:
                            messages_ref = conversations_ref.child(conversation_id).child('messages').child(message_id)
                            messages_ref.update({
                                "status": ChatMessageStatus.DELIVERED.value,
                                "updated_at": datetime.utcnow().isoformat()
                            })
                            break
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error marking message as delivered: {e}")
            return False
    
    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Delete a message (soft delete)"""
        try:
            # Check if user is the sender
            result = self.supabase.table("chat_messages").select("sender_id").eq("id", message_id).execute()
            
            if result.data and result.data[0]["sender_id"] == user_id:
                # Soft delete in Supabase
                self.supabase.table("chat_messages").update({
                    "content": "[Message deleted]",
                    "metadata": {"deleted": True, "deleted_at": datetime.utcnow().isoformat()},
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", message_id).execute()
                
                # Soft delete in Firebase if available
                if self.db_ref:
                    conversations_ref = self.db_ref.child('conversations')
                    conversations_snapshot = conversations_ref.get()
                    
                    for conversation_id, conv_data in conversations_snapshot.items():
                        if conv_data and 'messages' in conv_data:
                            messages = conv_data['messages']
                            if message_id in messages:
                                messages_ref = conversations_ref.child(conversation_id).child('messages').child(message_id)
                                messages_ref.update({
                                    "content": "[Message deleted]",
                                    "metadata": {"deleted": True, "deleted_at": datetime.utcnow().isoformat()},
                                    "updated_at": datetime.utcnow().isoformat()
                                })
                                break
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return False
    
    async def get_user_conversations_from_messages(self, user_id: str) -> List[ChatConversationResponse]:
        """Get all conversations where user is either sender or receiver from chat_messages table"""
        try:
            logger.info(f"Getting conversations from messages for user: {user_id}")
            
            # Get all messages where user is either sender or receiver
            # Try separate queries to debug
            sender_result = self.supabase.table("chat_messages").select("*").eq("sender_id", user_id).execute()
            recipient_result = self.supabase.table("chat_messages").select("*").eq("recipient_id", user_id).execute()
            
            logger.info(f"Sender messages: {len(sender_result.data)}")
            logger.info(f"Recipient messages: {len(recipient_result.data)}")
            
            # Combine results
            all_messages = sender_result.data + recipient_result.data
            logger.info(f"Total messages: {len(all_messages)}")
            
            # Remove duplicates based on message ID
            seen_ids = set()
            unique_messages = []
            for msg in all_messages:
                if msg["id"] not in seen_ids:
                    seen_ids.add(msg["id"])
                    unique_messages.append(msg)
            
            logger.info(f"Unique messages: {len(unique_messages)}")
            
            # Sort by created_at
            unique_messages.sort(key=lambda x: x["created_at"], reverse=True)
            
            logger.info(f"Processing {len(unique_messages)} unique messages")
            
            conversations = {}
            
            for msg in unique_messages:
                # Determine the other user in the conversation
                if msg["sender_id"] == user_id:
                    other_user_id = msg["recipient_id"]
                else:
                    other_user_id = msg["sender_id"]
                
                # Create conversation key
                conversation_key = f"{min(user_id, other_user_id)}_{max(user_id, other_user_id)}"
                
                if conversation_key not in conversations:
                    # Get other user details
                    other_user_details = await self._get_user_details(other_user_id)
                    
                    conversations[conversation_key] = {
                        "conversation_id": conversation_key,
                        "participant_id": other_user_id,
                        "participant_name": other_user_details.get("full_name") if other_user_details else "Unknown",
                        "participant_email": other_user_details.get("email") if other_user_details else None,
                        "last_message": None,
                        "unread_count": 0,
                        "last_activity": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                        "created_at": datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                    }
                
                # Update last message if this is more recent
                msg_created_at = datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00'))
                if conversations[conversation_key]["last_message"] is None or msg_created_at > conversations[conversation_key]["last_activity"]:
                    # Get sender and recipient details for the last message
                    sender_details = await self._get_user_details(msg["sender_id"])
                    recipient_details = await self._get_user_details(msg["recipient_id"])
                    
                    conversations[conversation_key]["last_message"] = ChatMessageResponse(
                        id=msg["id"],
                        sender_id=msg["sender_id"],
                        recipient_id=msg["recipient_id"],
                        message_type=ChatMessageType(msg["message_type"]),
                        content=msg["content"],
                        status=ChatMessageStatus(msg["status"]),
                        metadata=msg.get("metadata"),
                        created_at=msg_created_at,
                        updated_at=datetime.fromisoformat(msg["updated_at"].replace('Z', '+00:00')),
                        sender_name=sender_details.get("full_name") if sender_details else None,
                        sender_email=sender_details.get("email") if sender_details else None,
                        recipient_name=recipient_details.get("full_name") if recipient_details else None,
                        recipient_email=recipient_details.get("email") if recipient_details else None
                    )
                    conversations[conversation_key]["last_activity"] = msg_created_at
                
                # Count unread messages (only if current user is recipient)
                if msg["recipient_id"] == user_id and msg["status"] != ChatMessageStatus.READ.value:
                    conversations[conversation_key]["unread_count"] += 1
            
            # Ensure accepted mentorship relationships are included even if no messages
            try:
                # As mentee: accepted mentors
                mentee_mships = self.supabase.table("mentorship_interest").select(
                    "mentor_id, created_at, users!mentorship_interest_mentor_id_fkey(full_name, email)"
                ).eq("mentee_id", user_id).eq("status", "accepted").execute()
                # As mentor: accepted mentees
                mentor_mships = self.supabase.table("mentorship_interest").select(
                    "mentee_id, created_at, users!mentorship_interest_mentee_id_fkey(full_name, email)"
                ).eq("mentor_id", user_id).eq("status", "accepted").execute()

                def add_if_missing(other_id: str, created_at_str: str, user_info: Dict[str, Any]):
                    conversation_key = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
                    if conversation_key not in conversations:
                        participant_name = (user_info or {}).get("full_name") if user_info else "Unknown"
                        participant_email = (user_info or {}).get("email") if user_info else None
                        created_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        conversations[conversation_key] = {
                            "conversation_id": conversation_key,
                            "participant_id": other_id,
                            "participant_name": participant_name,
                            "participant_email": participant_email or "",
                            "last_message": None,
                            "unread_count": 0,
                            "last_activity": created_dt,
                            "created_at": created_dt,
                        }

                if mentee_mships.data:
                    for row in mentee_mships.data:
                        add_if_missing(row.get("mentor_id"), row.get("created_at"), row.get("users"))

                if mentor_mships.data:
                    for row in mentor_mships.data:
                        add_if_missing(row.get("mentee_id"), row.get("created_at"), row.get("users"))
            except Exception as e:
                logger.warning(f"Failed to enrich conversations with mentorships: {e}")

            # Convert to list and sort by last activity
            conversation_list = list(conversations.values())
            conversation_list.sort(key=lambda x: x["last_activity"], reverse=True)
            
            logger.info(f"Processed {len(conversation_list)} conversations (including mentorships)")
            
            return [ChatConversationResponse(**conv) for conv in conversation_list]
            
        except Exception as e:
            logger.error(f"Error getting user conversations from messages: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    async def get_conversation_history(self, user_id: str, other_user_id: str, limit: int = 50, offset: int = 0) -> List[ChatMessageResponse]:
        """Get paginated chat history between two users"""
        try:
            logger.info(f"Getting conversation history between {user_id} and {other_user_id}")
            
            # Get messages between the two users with pagination
            # Try separate queries first to debug
            user_to_other = self.supabase.table("chat_messages").select("*").eq("sender_id", user_id).eq("recipient_id", other_user_id).execute()
            other_to_user = self.supabase.table("chat_messages").select("*").eq("sender_id", other_user_id).eq("recipient_id", user_id).execute()
            
            logger.info(f"User to other messages: {len(user_to_other.data)}")
            logger.info(f"Other to user messages: {len(other_to_user.data)}")
            
            # Combine results
            all_messages = user_to_other.data + other_to_user.data
            logger.info(f"Total messages between users: {len(all_messages)}")
            
            # Remove duplicates and sort
            seen_ids = set()
            unique_messages = []
            for msg in all_messages:
                if msg["id"] not in seen_ids:
                    seen_ids.add(msg["id"])
                    unique_messages.append(msg)
            
            # Sort by created_at descending, then apply pagination
            unique_messages.sort(key=lambda x: x["created_at"], reverse=True)
            paginated_messages = unique_messages[offset:offset + limit]
            
            logger.info(f"Paginated messages: {len(paginated_messages)}")
            
            messages = []
            for msg in paginated_messages:
                # Get sender and recipient details
                sender_details = await self._get_user_details(msg["sender_id"])
                recipient_details = await self._get_user_details(msg["recipient_id"])
                
                messages.append(ChatMessageResponse(
                    id=msg["id"],
                    sender_id=msg["sender_id"],
                    recipient_id=msg["recipient_id"],
                    message_type=ChatMessageType(msg["message_type"]),
                    content=msg["content"],
                    status=ChatMessageStatus(msg["status"]),
                    metadata=msg.get("metadata"),
                    created_at=datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(msg["updated_at"].replace('Z', '+00:00')),
                    sender_name=sender_details.get("full_name") if sender_details else None,
                    sender_email=sender_details.get("email") if sender_details else None,
                    recipient_name=recipient_details.get("full_name") if recipient_details else None,
                    recipient_email=recipient_details.get("email") if recipient_details else None
                ))
            
            # Sort by created_at ascending (oldest first) for proper chat history order
            messages.sort(key=lambda x: x.created_at)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def _get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details by user_id"""
        try:
            result = self.supabase.table("users").select("full_name, email").eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None

# Service instance
firebase_chat_service = FirebaseChatService()
