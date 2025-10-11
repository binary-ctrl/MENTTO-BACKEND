from fastapi import HTTPException, status
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_supabase_client
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_user_id_from_token
)
from app.auth.schemas import UserCreate, UserLogin, TokenResponse
from app.profile.service import ensure_minimal_profile
from app.utils.email_utils import send_welcome_email
from app.utils.klaviyo import get_klaviyo_client
import asyncio
import random
import string

def generate_user_id():
    """Generate a random 10-digit user ID that doesn't start with 0"""
    return str(random.randint(10**9, 10**10 - 1))

class AuthService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.table = self.supabase.table('users')

    async def signup(self, user: UserCreate) -> TokenResponse:
        try:
            # Check if user already exists
            select_query = self.table.select("*").eq("email", user.email)
            existing_user = await asyncio.to_thread(select_query.execute)
            if existing_user.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            # Create new user
            hashed_password = await asyncio.to_thread(get_password_hash, user.password)
            user_id = generate_user_id()
            new_user = {
                "user_id": user_id,
                "email": user.email,
                "password_hash": hashed_password,
                "full_name": user.full_name,
                "role": "",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            insert_op = self.table.insert(new_user)
            result = await asyncio.to_thread(insert_op.execute)
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )

            user_id = result.data[0]["user_id"]
            
            # Generate access token
            access_token = create_access_token(
                data={"sub": user_id, "full_name": user.full_name},
                user_id=user_id
            )

            # Ensure minimal profile exists for this user (run in background)
            try:
                asyncio.create_task(asyncio.to_thread(ensure_minimal_profile, user_id, full_name=user.full_name))
            except Exception:
                pass

            # Fire-and-forget welcome email
            try:
                asyncio.create_task(send_welcome_email(user.email, user.full_name))
            except Exception:
                pass

            # Fire-and-forget Klaviyo "Signed Up" event
            try:
                klaviyo = get_klaviyo_client()
                asyncio.create_task(
                    klaviyo.track_signed_up(
                        email=user.email,
                        full_name=user.full_name,
                        user_id=user_id,
                        metadata={"source": "password_signup"}
                    )
                )
            except Exception:
                pass

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                message="User created successfully"
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    async def login(self, user: UserLogin) -> TokenResponse:
        try:
            # Get user by email
            select_query = self.table.select("*").eq("email", user.email)
            result = await asyncio.to_thread(select_query.execute)
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password"
                )

            db_user = result.data[0]

            # Verify password
            is_valid = await asyncio.to_thread(verify_password, user.password, db_user["password_hash"])
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password"
                )

            user_id = db_user["user_id"]
            
            # Get user role from database
            user_role = db_user.get("role", "")
            user_roles = [user_role] if user_role else []
            
            # Generate access token
            access_token = create_access_token(
                data={"sub": user_id, "full_name": db_user.get("full_name", "")},
                user_id=user_id,
                roles=user_roles
            )

            # Ensure minimal profile exists (and backfill name if needed) in background
            try:
                asyncio.create_task(asyncio.to_thread(ensure_minimal_profile, user_id, full_name=db_user.get("full_name")))
            except Exception:
                pass

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                message="Login successful"
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            ) 