"""
Admin Authentication Dependencies
"""

import logging
from fastapi import HTTPException, status, Depends
from typing import Optional

from app.core.security.auth_dependencies import get_current_user
from app.services.admin.admin_service import admin_service

logger = logging.getLogger(__name__)

async def get_current_admin(current_user = Depends(get_current_user)):
    """
    Dependency to get current admin user
    Only users who are in the admin_accounts table can access admin endpoints
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Get user_id from current_user (handle both object and dict)
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token - user_id not found"
            )
        
        # Check if user is an admin
        is_admin = await admin_service.is_admin_user(user_id)
        
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required. Your account is not authorized to perform this action."
            )
        
        # Get admin account details
        admin_account = await admin_service.get_admin_account(user_id)
        
        if not admin_account:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account not found or inactive"
            )
        
        # Return admin account with user details
        return {
            "user_id": user_id,
            "email": admin_account.email,
            "is_admin": True,
            "admin_account_id": admin_account.id,
            "user_details": current_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )
