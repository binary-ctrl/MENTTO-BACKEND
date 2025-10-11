"""
Calendar Credentials Service for managing Google Calendar OAuth tokens
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.database import get_supabase

logger = logging.getLogger(__name__)

class CalendarCredentialsService:
    def __init__(self):
        self.supabase = get_supabase()

    async def store_calendar_credentials(self, user_id: str, credentials_data: Dict[str, Any]) -> bool:
        """Store Google Calendar credentials for a user"""
        try:
            # Add timestamp for when credentials were stored
            credentials_with_metadata = {
                **credentials_data,
                'stored_at': datetime.utcnow().isoformat(),
                'last_sync': None  # Will be updated when sync happens
            }
            
            # Update user's calendar credentials
            result = self.supabase.table("users").update({
                "google_calendar_credentials": credentials_with_metadata
            }).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"Successfully stored calendar credentials for user {user_id}")
                return True
            else:
                logger.error(f"Failed to store calendar credentials for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing calendar credentials for user {user_id}: {e}")
            return False

    async def get_calendar_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stored Google Calendar credentials for a user"""
        try:
            result = self.supabase.table("users").select("google_calendar_credentials").eq("user_id", user_id).execute()
            
            if result.data and result.data[0].get("google_calendar_credentials"):
                credentials = result.data[0]["google_calendar_credentials"]
                logger.info(f"Retrieved calendar credentials for user {user_id}")
                return credentials
            else:
                logger.info(f"No calendar credentials found for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving calendar credentials for user {user_id}: {e}")
            return None

    async def has_calendar_credentials(self, user_id: str) -> bool:
        """Check if user has stored calendar credentials"""
        credentials = await self.get_calendar_credentials(user_id)
        return credentials is not None

    async def update_last_sync(self, user_id: str, sync_timestamp: Optional[datetime] = None) -> bool:
        """Update the last sync timestamp for a user's calendar credentials"""
        try:
            if not sync_timestamp:
                sync_timestamp = datetime.utcnow()
            
            # Get current credentials
            credentials = await self.get_calendar_credentials(user_id)
            if not credentials:
                logger.warning(f"No credentials found to update sync time for user {user_id}")
                return False
            
            # Update last sync time
            credentials['last_sync'] = sync_timestamp.isoformat()
            
            # Store updated credentials
            result = self.supabase.table("users").update({
                "google_calendar_credentials": credentials
            }).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"Updated last sync time for user {user_id}")
                return True
            else:
                logger.error(f"Failed to update last sync time for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating last sync time for user {user_id}: {e}")
            return False

    async def revoke_calendar_credentials(self, user_id: str) -> bool:
        """Remove stored calendar credentials for a user"""
        try:
            result = self.supabase.table("users").update({
                "google_calendar_credentials": None
            }).eq("user_id", user_id).execute()
            
            if result.data:
                logger.info(f"Successfully revoked calendar credentials for user {user_id}")
                return True
            else:
                logger.error(f"Failed to revoke calendar credentials for user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error revoking calendar credentials for user {user_id}: {e}")
            return False

    async def get_calendar_status(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive calendar status for a user"""
        try:
            credentials = await self.get_calendar_credentials(user_id)
            
            if not credentials:
                return {
                    "user_id": user_id,
                    "calendar_connected": False,
                    "last_sync": None,
                    "credentials_stored_at": None,
                    "message": "Calendar not connected"
                }
            
            return {
                "user_id": user_id,
                "calendar_connected": True,
                "last_sync": credentials.get("last_sync"),
                "credentials_stored_at": credentials.get("stored_at"),
                "scopes": credentials.get("scopes", []),
                "message": "Calendar connected and ready for sync"
            }
            
        except Exception as e:
            logger.error(f"Error getting calendar status for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "calendar_connected": False,
                "error": str(e),
                "message": "Error checking calendar status"
            }

# Service instance
calendar_credentials_service = CalendarCredentialsService()
