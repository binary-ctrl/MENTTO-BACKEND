"""
Notification Service for handling in-app notifications
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from database import get_supabase
from models import (
    NotificationCreate, 
    NotificationResponse, 
    NotificationUpdate,
    NotificationSummary,
    BulkNotificationUpdate,
    NotificationType,
    NotificationPriority,
    NotificationStatus
)

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.supabase = get_supabase()
    
    async def create_notification(self, notification_data: NotificationCreate) -> NotificationResponse:
        """Create a new notification"""
        try:
            notification_id = str(uuid.uuid4())
            notification_record = {
                "id": notification_id,
                "recipient_id": notification_data.recipient_id,
                "notification_type": notification_data.notification_type.value,
                "title": notification_data.title,
                "message": notification_data.message,
                "priority": notification_data.priority.value,
                "status": NotificationStatus.UNREAD.value,
                "metadata": notification_data.metadata or {},
                "action_url": notification_data.action_url,
                "expires_at": notification_data.expires_at.isoformat() if notification_data.expires_at else None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert notification into database
            result = self.supabase.table("notifications").insert(notification_record).execute()
            
            if result.data:
                # Get sender details if available in metadata
                sender_name = None
                sender_email = None
                if notification_data.metadata and "sender_id" in notification_data.metadata:
                    sender_details = await self._get_user_details(notification_data.metadata["sender_id"])
                    if sender_details:
                        sender_name = sender_details.get("full_name")
                        sender_email = sender_details.get("email")
                
                response = NotificationResponse(
                    id=notification_id,
                    recipient_id=notification_data.recipient_id,
                    notification_type=notification_data.notification_type,
                    title=notification_data.title,
                    message=notification_data.message,
                    priority=notification_data.priority,
                    status=NotificationStatus.UNREAD,
                    metadata=notification_data.metadata,
                    action_url=notification_data.action_url,
                    expires_at=notification_data.expires_at,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    sender_name=sender_name,
                    sender_email=sender_email
                )
                
                return response
            else:
                raise Exception("Failed to insert notification into database")
                
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise
    
    async def get_user_notifications(
        self, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None
    ) -> List[NotificationResponse]:
        """Get notifications for a user"""
        try:
            query = self.supabase.table("notifications").select("*")
            query = query.eq("recipient_id", user_id)
            
            if status:
                query = query.eq("status", status.value)
            if notification_type:
                query = query.eq("notification_type", notification_type.value)
            
            # Filter out expired notifications
            query = query.or_("expires_at.is.null,expires_at.gt." + datetime.utcnow().isoformat())
            
            result = query.order("created_at", desc=True).limit(limit).offset(offset).execute()
            
            notifications = []
            for notif in result.data:
                notification = NotificationResponse(
                    id=notif["id"],
                    recipient_id=notif["recipient_id"],
                    notification_type=NotificationType(notif["notification_type"]),
                    title=notif["title"],
                    message=notif["message"],
                    priority=NotificationPriority(notif["priority"]),
                    status=NotificationStatus(notif["status"]),
                    metadata=notif.get("metadata", {}),
                    action_url=notif.get("action_url"),
                    expires_at=datetime.fromisoformat(notif["expires_at"].replace('Z', '+00:00')) if notif.get("expires_at") else None,
                    created_at=datetime.fromisoformat(notif["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(notif["updated_at"].replace('Z', '+00:00')),
                    read_at=datetime.fromisoformat(notif["read_at"].replace('Z', '+00:00')) if notif.get("read_at") else None
                )
                notifications.append(notification)
            
            return notifications
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            raise
    
    async def get_notification_summary(self, user_id: str) -> NotificationSummary:
        """Get notification summary for a user"""
        try:
            # Get total unread count
            unread_result = self.supabase.table("notifications").select("notification_type").eq("recipient_id", user_id).eq("status", NotificationStatus.UNREAD.value).execute()
            
            total_unread = len(unread_result.data)
            
            # Count by type
            unread_by_type = {}
            for notif in unread_result.data:
                notif_type = notif["notification_type"]
                unread_by_type[notif_type] = unread_by_type.get(notif_type, 0) + 1
            
            # Get recent notifications (last 5)
            recent_result = self.supabase.table("notifications").select("*").eq("recipient_id", user_id).order("created_at", desc=True).limit(5).execute()
            
            recent_notifications = []
            for notif in recent_result.data:
                notification = NotificationResponse(
                    id=notif["id"],
                    recipient_id=notif["recipient_id"],
                    notification_type=NotificationType(notif["notification_type"]),
                    title=notif["title"],
                    message=notif["message"],
                    priority=NotificationPriority(notif["priority"]),
                    status=NotificationStatus(notif["status"]),
                    metadata=notif.get("metadata", {}),
                    action_url=notif.get("action_url"),
                    expires_at=datetime.fromisoformat(notif["expires_at"].replace('Z', '+00:00')) if notif.get("expires_at") else None,
                    created_at=datetime.fromisoformat(notif["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(notif["updated_at"].replace('Z', '+00:00')),
                    read_at=datetime.fromisoformat(notif["read_at"].replace('Z', '+00:00')) if notif.get("read_at") else None
                )
                recent_notifications.append(notification)
            
            return NotificationSummary(
                total_unread=total_unread,
                unread_by_type=unread_by_type,
                recent_notifications=recent_notifications
            )
            
        except Exception as e:
            logger.error(f"Error getting notification summary: {e}")
            raise
    
    async def mark_notification_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        try:
            result = self.supabase.table("notifications").update({
                "status": NotificationStatus.READ.value,
                "read_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", notification_id).eq("recipient_id", user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    async def mark_all_notifications_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user"""
        try:
            result = self.supabase.table("notifications").update({
                "status": NotificationStatus.READ.value,
                "read_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("recipient_id", user_id).eq("status", NotificationStatus.UNREAD.value).execute()
            
            return len(result.data)
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0
    
    async def update_notification(self, notification_id: str, user_id: str, update_data: NotificationUpdate) -> bool:
        """Update a notification"""
        try:
            update_dict = {"updated_at": datetime.utcnow().isoformat()}
            
            if update_data.status:
                update_dict["status"] = update_data.status.value
                if update_data.status == NotificationStatus.READ and not update_data.read_at:
                    update_dict["read_at"] = datetime.utcnow().isoformat()
            
            if update_data.read_at:
                update_dict["read_at"] = update_data.read_at.isoformat()
            
            result = self.supabase.table("notifications").update(update_dict).eq("id", notification_id).eq("recipient_id", user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error updating notification: {e}")
            return False
    
    async def bulk_update_notifications(self, user_id: str, update_data: BulkNotificationUpdate) -> int:
        """Bulk update notifications"""
        try:
            update_dict = {
                "status": update_data.status.value,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if update_data.status == NotificationStatus.READ:
                update_dict["read_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("notifications").update(update_dict).in_("id", update_data.notification_ids).eq("recipient_id", user_id).execute()
            
            return len(result.data)
            
        except Exception as e:
            logger.error(f"Error bulk updating notifications: {e}")
            return 0
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification"""
        try:
            result = self.supabase.table("notifications").delete().eq("id", notification_id).eq("recipient_id", user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False
    
    async def cleanup_expired_notifications(self) -> int:
        """Clean up expired notifications"""
        try:
            result = self.supabase.table("notifications").delete().lt("expires_at", datetime.utcnow().isoformat()).execute()
            
            return len(result.data)
            
        except Exception as e:
            logger.error(f"Error cleaning up expired notifications: {e}")
            return 0
    
    async def create_system_notification(
        self, 
        recipient_id: str, 
        title: str, 
        message: str, 
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        action_url: Optional[str] = None,
        expires_in_days: Optional[int] = None
    ) -> NotificationResponse:
        """Create a system notification"""
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        notification_data = NotificationCreate(
            recipient_id=recipient_id,
            notification_type=NotificationType.SYSTEM,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            expires_at=expires_at
        )
        
        return await self.create_notification(notification_data)
    
    async def _get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details by user_id"""
        try:
            result = self.supabase.table("users").select("full_name, email").eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None

# Service instance
notification_service = NotificationService()
