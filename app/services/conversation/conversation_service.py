"""
Conversation Service for managing chat conversations
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import get_supabase
from app.models.models import ConversationSummary, ConversationMessage

logger = logging.getLogger(__name__)

class ConversationService:
    def __init__(self):
        self.supabase = get_supabase()

    async def get_mentee_conversations(self, mentee_id: str) -> List[ConversationSummary]:
        """Get all conversations for a mentee with accepted mentorships"""
        try:
            # First, get all accepted mentorship interests for the mentee
            mentorship_query = self.supabase.table("mentorship_interest").select(
                "id, mentor_id, created_at, updated_at, users!mentorship_interest_mentor_id_fkey(full_name, email)"
            ).eq("mentee_id", mentee_id).eq("status", "accepted").execute()
            
            if not mentorship_query.data:
                logger.info(f"No accepted mentorships found for mentee {mentee_id}")
                return []
            
            conversations = []
            
            for mentorship in mentorship_query.data:
                mentor_id = mentorship["mentor_id"]
                mentorship_id = mentorship["id"]
                mentor_info = mentorship.get("users", {})
                mentor_name = mentor_info.get("full_name", "Unknown")
                mentor_email = mentor_info.get("email", "")
                
                # Get the last message between mentee and mentor
                last_message = await self._get_last_message(mentee_id, mentor_id)
                
                # Get unread message count (messages sent by mentor to mentee that are not read)
                unread_count = await self._get_unread_count(mentee_id, mentor_id)
                
                # Get total message count between mentee and mentor
                total_messages = await self._get_total_message_count(mentee_id, mentor_id)
                
                # Determine last activity time
                last_activity = None
                if last_message:
                    last_activity = last_message.created_at
                else:
                    # If no messages, use mentorship creation time
                    last_activity = datetime.fromisoformat(mentorship["created_at"].replace('Z', '+00:00'))
                
                conversation = ConversationSummary(
                    mentor_id=mentor_id,
                    mentor_name=mentor_name,
                    mentor_email=mentor_email,
                    mentorship_interest_id=mentorship_id,
                    last_message=last_message,
                    unread_count=unread_count,
                    total_messages=total_messages,
                    last_activity=last_activity,
                    is_online=False  # Could be extended with real-time status
                )
                
                conversations.append(conversation)
            
            # Sort conversations by last activity (most recent first)
            conversations.sort(key=lambda x: x.last_activity or datetime.min, reverse=True)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for mentee {mentee_id}: {e}")
            return []

    async def get_mentor_conversations(self, mentor_id: str) -> List[ConversationSummary]:
        """Get all conversations for a mentor with accepted mentorships"""
        try:
            # First, get all accepted mentorship interests for the mentor
            mentorship_query = self.supabase.table("mentorship_interest").select(
                "id, mentee_id, created_at, updated_at, users!mentorship_interest_mentee_id_fkey(full_name, email)"
            ).eq("mentor_id", mentor_id).eq("status", "accepted").execute()
            
            if not mentorship_query.data:
                logger.info(f"No accepted mentorships found for mentor {mentor_id}")
                return []
            
            conversations = []
            
            for mentorship in mentorship_query.data:
                mentee_id = mentorship["mentee_id"]
                mentorship_id = mentorship["id"]
                mentee_info = mentorship.get("users", {})
                mentee_name = mentee_info.get("full_name", "Unknown")
                mentee_email = mentee_info.get("email", "")
                
                # Get the last message between mentor and mentee
                last_message = await self._get_last_message(mentor_id, mentee_id)
                
                # Get unread message count (messages sent by mentee to mentor that are not read)
                unread_count = await self._get_unread_count(mentor_id, mentee_id)
                
                # Get total message count between mentor and mentee
                total_messages = await self._get_total_message_count(mentor_id, mentee_id)
                
                # Determine last activity time
                last_activity = None
                if last_message:
                    last_activity = last_message.created_at
                else:
                    # If no messages, use mentorship creation time
                    last_activity = datetime.fromisoformat(mentorship["created_at"].replace('Z', '+00:00'))
                
                conversation = ConversationSummary(
                    mentor_id=mentee_id,  # For mentor view, this represents the mentee
                    mentor_name=mentee_name,
                    mentor_email=mentee_email,
                    mentorship_interest_id=mentorship_id,
                    last_message=last_message,
                    unread_count=unread_count,
                    total_messages=total_messages,
                    last_activity=last_activity,
                    is_online=False  # Could be extended with real-time status
                )
                
                conversations.append(conversation)
            
            # Sort conversations by last activity (most recent first)
            conversations.sort(key=lambda x: x.last_activity or datetime.min, reverse=True)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for mentor {mentor_id}: {e}")
            return []

    async def _get_last_message(self, user1_id: str, user2_id: str) -> Optional[ConversationMessage]:
        """Get the last message between two users"""
        try:
            # Get the most recent message between the two users (either direction)
            # Use separate queries and combine results due to Supabase client limitations
            result1 = self.supabase.table("chat_messages").select(
                "*, users!chat_messages_sender_id_fkey(full_name, email)"
            ).eq("sender_id", user1_id).eq("recipient_id", user2_id).order("created_at", desc=True).limit(1).execute()
            
            result2 = self.supabase.table("chat_messages").select(
                "*, users!chat_messages_sender_id_fkey(full_name, email)"
            ).eq("sender_id", user2_id).eq("recipient_id", user1_id).order("created_at", desc=True).limit(1).execute()
            
            # Combine and find the most recent
            all_messages = []
            if result1.data:
                all_messages.extend(result1.data)
            if result2.data:
                all_messages.extend(result2.data)
            
            if all_messages:
                # Sort by created_at and get the most recent
                all_messages.sort(key=lambda x: x["created_at"], reverse=True)
                result_data = [all_messages[0]]
            else:
                result_data = []
            
            if result_data:
                message_data = result_data[0]
                return self._convert_to_conversation_message(message_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting last message between {user1_id} and {user2_id}: {e}")
            return None

    async def _get_unread_count(self, user_id: str, other_user_id: str) -> int:
        """Get count of unread messages from other_user_id to user_id"""
        try:
            result = self.supabase.table("chat_messages").select(
                "id", count="exact"
            ).eq("sender_id", other_user_id).eq("recipient_id", user_id).eq("status", "sent").execute()
            
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Error getting unread count for {user_id} from {other_user_id}: {e}")
            return 0

    async def _get_total_message_count(self, user1_id: str, user2_id: str) -> int:
        """Get total message count between two users"""
        try:
            # Use separate queries and combine results
            result1 = self.supabase.table("chat_messages").select(
                "id", count="exact"
            ).eq("sender_id", user1_id).eq("recipient_id", user2_id).execute()
            
            result2 = self.supabase.table("chat_messages").select(
                "id", count="exact"
            ).eq("sender_id", user2_id).eq("recipient_id", user1_id).execute()
            
            # Combine counts
            count1 = result1.count or 0
            count2 = result2.count or 0
            total_count = count1 + count2
            
            return total_count
            
        except Exception as e:
            logger.error(f"Error getting total message count between {user1_id} and {user2_id}: {e}")
            return 0

    async def get_conversation_messages(self, user1_id: str, user2_id: str, limit: int = 50, offset: int = 0) -> List[ConversationMessage]:
        """Get conversation messages between two users"""
        try:
            # Use separate queries and combine results
            result1 = self.supabase.table("chat_messages").select(
                "*, users!chat_messages_sender_id_fkey(full_name, email)"
            ).eq("sender_id", user1_id).eq("recipient_id", user2_id).order("created_at", desc=True).execute()
            
            result2 = self.supabase.table("chat_messages").select(
                "*, users!chat_messages_sender_id_fkey(full_name, email)"
            ).eq("sender_id", user2_id).eq("recipient_id", user1_id).order("created_at", desc=True).execute()
            
            # Combine all messages
            all_messages = []
            if result1.data:
                all_messages.extend(result1.data)
            if result2.data:
                all_messages.extend(result2.data)
            
            # Sort by created_at (most recent first)
            all_messages.sort(key=lambda x: x["created_at"], reverse=True)
            
            # Apply pagination
            paginated_messages = all_messages[offset:offset + limit]
            
            messages = []
            for message_data in paginated_messages:
                message = self._convert_to_conversation_message(message_data)
                if message:
                    messages.append(message)
            
            # Return messages in chronological order (oldest first)
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"Error getting conversation messages between {user1_id} and {user2_id}: {e}")
            return []

    def _convert_to_conversation_message(self, message_data: Dict[str, Any]) -> Optional[ConversationMessage]:
        """Convert database record to ConversationMessage"""
        try:
            # Extract sender details from joined user data
            sender_name = None
            sender_email = None
            if message_data.get("users"):
                sender_name = message_data["users"].get("full_name")
                sender_email = message_data["users"].get("email")
            
            return ConversationMessage(
                id=message_data["id"],
                sender_id=message_data["sender_id"],
                recipient_id=message_data["recipient_id"],
                message_type=message_data["message_type"],
                content=message_data["content"],
                status=message_data["status"],
                metadata=message_data.get("metadata"),
                created_at=datetime.fromisoformat(message_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(message_data["updated_at"].replace('Z', '+00:00')),
                sender_name=sender_name,
                sender_email=sender_email
            )
        except Exception as e:
            logger.error(f"Error converting message data to ConversationMessage: {e}")
            return None

# Service instance
conversation_service = ConversationService()
