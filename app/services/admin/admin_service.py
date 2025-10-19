"""
Admin Service for managing admin accounts and mentor verification
"""

import logging
from typing import Optional, List
from datetime import datetime

from app.core.database import get_supabase, get_supabase_admin
from app.models.models import AdminAccountCreate, AdminAccountResponse, MentorVerificationUpdate

logger = logging.getLogger(__name__)

class AdminService:
    def __init__(self):
        self.supabase = get_supabase()
        self.supabase_admin = get_supabase_admin()

    async def is_admin_user(self, user_id: str) -> bool:
        """Check if a user is an admin"""
        try:
            result = self.supabase.table("admin_accounts").select("id").eq("user_id", user_id).eq("is_active", True).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
            return False

    async def get_admin_account(self, user_id: str) -> Optional[AdminAccountResponse]:
        """Get admin account by user_id"""
        try:
            result = self.supabase.table("admin_accounts").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            
            if result.data:
                data = result.data[0]
                return AdminAccountResponse(
                    id=data["id"],
                    user_id=data["user_id"],
                    email=data["email"],
                    is_active=data["is_active"],
                    created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                )
            return None
        except Exception as e:
            logger.error(f"Error getting admin account for user {user_id}: {e}")
            return None

    async def create_admin_account(self, admin_data: AdminAccountCreate) -> AdminAccountResponse:
        """Create a new admin account"""
        try:
            # Check if user exists in users table
            user_result = self.supabase.table("users").select("user_id, email").eq("user_id", admin_data.user_id).execute()
            if not user_result.data:
                raise Exception("User not found in users table")
            
            user_email = user_result.data[0]["email"]
            
            # Check if admin account already exists
            existing = await self.get_admin_account(admin_data.user_id)
            if existing:
                raise Exception("Admin account already exists for this user")
            
            # Create admin account
            admin_dict = {
                "user_id": admin_data.user_id,
                "email": user_email,  # Use email from users table
                "is_active": admin_data.is_active
            }
            
            result = self.supabase.table("admin_accounts").insert(admin_dict).execute()
            
            if result.data:
                data = result.data[0]
                return AdminAccountResponse(
                    id=data["id"],
                    user_id=data["user_id"],
                    email=data["email"],
                    is_active=data["is_active"],
                    created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                )
            else:
                raise Exception("Failed to create admin account")
                
        except Exception as e:
            logger.error(f"Error creating admin account: {e}")
            raise

    async def update_mentor_verification_status(
        self, 
        mentor_user_id: str, 
        verification_data: MentorVerificationUpdate,
        admin_user_id: str
    ) -> bool:
        """Update mentor verification status"""
        try:
            # Check if mentor exists
            mentor_result = self.supabase.table("mentor_details").select("user_id").eq("user_id", mentor_user_id).execute()
            if not mentor_result.data:
                raise Exception("Mentor not found")
            
            # Update verification status
            update_data = {
                "verification_status": verification_data.verification_status.value,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Add admin notes if provided
            if verification_data.admin_notes:
                update_data["admin_notes"] = verification_data.admin_notes
                update_data["verified_by"] = admin_user_id
                update_data["verified_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table("mentor_details").update(update_data).eq("user_id", mentor_user_id).execute()
            
            if result.data:
                logger.info(f"Mentor {mentor_user_id} verification status updated to {verification_data.verification_status.value} by admin {admin_user_id}")
                return True
            else:
                raise Exception("Failed to update mentor verification status")
                
        except Exception as e:
            logger.error(f"Error updating mentor verification status: {e}")
            raise

    async def get_all_admin_accounts(self) -> List[AdminAccountResponse]:
        """Get all admin accounts"""
        try:
            result = self.supabase.table("admin_accounts").select("*").eq("is_active", True).execute()
            
            admin_accounts = []
            for data in result.data:
                admin_accounts.append(AdminAccountResponse(
                    id=data["id"],
                    user_id=data["user_id"],
                    email=data["email"],
                    is_active=data["is_active"],
                    created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                ))
            
            return admin_accounts
        except Exception as e:
            logger.error(f"Error getting all admin accounts: {e}")
            raise

# Create a singleton instance
admin_service = AdminService()
