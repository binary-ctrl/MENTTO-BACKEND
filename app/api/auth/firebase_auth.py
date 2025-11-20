"""
Firebase Authentication Implementation for FastAPI
Handles Firebase Auth with JWT token generation
"""

import os
import asyncio
import secrets
import random
import httpx
import jwt
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Response, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import json

from app.core.config import settings
from app.core.security import create_access_token, get_user_id_from_token
from app.core.database import get_supabase
from app.services.user.services import user_service
from app.services.auth.mfa_service import mfa_service
from app.utils.url_utils import format_auth_url
# from app.profile.service import ensure_minimal_profile  # Commented out - module doesn't exist
# from app.utils.email_utils import send_welcome_email  # Commented out - module doesn't exist
# from app.utils.klaviyo import get_klaviyo_client  # Commented out - module doesn't exist
try:
    # Ensure agentv2 session can be created at login/signup time
    from agentv2.session_manager import Agentv2SessionManager
except Exception:
    Agentv2SessionManager = None

router = APIRouter(prefix="/auth/firebase", tags=["firebase_auth"])

# Logger
logger = logging.getLogger(__name__)

# Firebase Configuration
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Firebase Auth endpoints
FIREBASE_AUTH_URL = f"https://{FIREBASE_AUTH_DOMAIN}/__/auth/handler"

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

class FirebaseUserInfo(BaseModel):
    uid: str
    email: str
    email_verified: bool
    display_name: Optional[str] = None
    photo_url: Optional[str] = None

class UserProfileUpdate(BaseModel):
    user_id: str
    user_type: str
    description: Optional[str] = None

class UpdateRoleFollowUpRequest(BaseModel):
    role: Optional[str] = None
    follow_up: Optional[str] = None

# Allowed user roles for updates
ALLOWED_USER_ROLES = [
    "Founder",
    "Partner",
    "Freelancer",
    "Mentor/Incubator",
    "Job Seeker/Side Hustle",
    "Investor",
    "Student",
]

def validate_firebase_config():
    """Validate that Firebase configuration is complete"""
    if not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Firebase not configured: FIREBASE_API_KEY missing"
        )
    if not FIREBASE_PROJECT_ID:
        raise HTTPException(
            status_code=500, 
            detail="Firebase not configured: FIREBASE_PROJECT_ID missing"
        )
    if not FIREBASE_AUTH_DOMAIN:
        raise HTTPException(
            status_code=500, 
            detail="Firebase not configured: FIREBASE_AUTH_DOMAIN missing"
        )

async def verify_firebase_token(id_token: str) -> FirebaseUserInfo:
    """Verify Firebase ID token and get user info"""
    try:
        # Decode the JWT token (this is a simplified version)
        # In production, you should verify the token signature with Firebase
        decoded = jwt.decode(id_token, options={"verify_signature": False})
        
        # Debug: Print decoded token to see what's available
        print(f"DEBUG: Decoded token: {decoded}")
        
        # Extract email from Firebase ID token
        email = decoded.get("email")
        user_id = decoded.get("user_id") or decoded.get("sub")
        
        if not email or not user_id:
            print(f"DEBUG: Missing email or user_id in token! email={email}, user_id={user_id}")
            raise HTTPException(
                status_code=401,
                detail="Email or user_id not found in Firebase token"
            )
        
        print(f"DEBUG: Extracted email: {email}")
        print(f"DEBUG: Extracted user_id: {user_id}")
        
        # Try to get display name from various possible fields in Firebase token
        display_name = (
            decoded.get("name") or 
            decoded.get("display_name") or 
            decoded.get("displayName") or 
            decoded.get("full_name") or 
            decoded.get("fullName") or 
            "User"
        )
        
        print(f"DEBUG: Extracted display_name: {display_name}")
        
        return FirebaseUserInfo(
            uid=user_id,
            email=email,
            email_verified=decoded.get("email_verified", True),
            display_name=display_name,
            photo_url=decoded.get("picture")
        )
    except Exception as e:
        print(f"DEBUG: Error verifying token: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid Firebase token: {str(e)}"
        )

async def find_or_create_user(firebase_user: FirebaseUserInfo, role: str = "", do_backfill: bool = True) -> Dict[str, Any]:
    """Find existing user by Firebase UID or create new user"""
    
    print(f"DEBUG: Processing user - Email: {firebase_user.email}, UID: {firebase_user.uid}")
    print(f"DEBUG: Requested role: {role}")
    
    # Check if user exists by email using user service
    existing_user = await user_service.get_user_by_email(firebase_user.email)
    
    print(f"DEBUG: Existing user query result: {existing_user}")
    print(f"DEBUG: Looking for email: '{firebase_user.email}'")
    
    if existing_user:
        # User exists, return existing user data
        # existing_user is a UserResponse object, access its attributes directly
        serialized_user_data = {
            "user_id": existing_user.user_id,
            "email": existing_user.email,
            "full_name": existing_user.full_name,
            "role": existing_user.role
        }
        print(f"DEBUG: Found existing user: {serialized_user_data}")
        
        # Backfill full_name if requested
        if do_backfill:
            try:
                current_name = (serialized_user_data.get("full_name") or "").strip()
                requested_name = (firebase_user.display_name or "").strip()
                if requested_name and (current_name == "" or current_name.lower() == "user"):
                    print(f"DEBUG: Updating full_name from '{current_name}' to '{requested_name}'")
                    try:
                        supabase = get_supabase()
                        update_op = supabase.table("users").update({"full_name": requested_name}).eq("user_id", serialized_user_data["user_id"]) 
                        update_result = await asyncio.to_thread(update_op.execute)
                        print(f"DEBUG: full_name update result: {update_result.data}")
                        serialized_user_data["full_name"] = requested_name
                    except Exception as e:
                        print(f"DEBUG: Failed to update full_name: {str(e)}")
            except Exception as e:
                print(f"DEBUG: Error during full_name backfill logic: {str(e)}")

        # Check if user has a role, if not, update with the requested role
        current_role = serialized_user_data.get("role", "")
        if do_backfill and current_role == "" and role != "":
            print(f"DEBUG: Updating existing user role from '{current_role}' to '{role}'")
            # Update the user's role in the database
            try:
                supabase = get_supabase_client()
                update_op = supabase.table("users").update({"role": role}).eq("user_id", serialized_user_data["user_id"]) 
                update_result = await asyncio.to_thread(update_op.execute)
                print(f"DEBUG: Role update result: {update_result.data}")
                serialized_user_data["role"] = role
            except Exception as e:
                print(f"DEBUG: Failed to update role: {str(e)}")
        
        return {
            "user_id": serialized_user_data["user_id"],
            "email": serialized_user_data["email"],
            "full_name": serialized_user_data["full_name"],
            "is_new_user": False,
            "role": serialized_user_data.get("role", "") # Get role from user data
        }
    else:
        # Create new user with simple function
        user_id = str(random.randint(10**9, 10**10 - 1))  # Generate 10-digit user ID that doesn't start with 0
        print(f"DEBUG: Creating new user with ID: {user_id}")
        
        created_at = datetime.utcnow().isoformat()
        updated_at = datetime.utcnow().isoformat()
        
        print(f"DEBUG: Insert params: ({user_id}, {firebase_user.email}, {firebase_user.display_name or 'User'}, {created_at}, {updated_at}, role: {role})")
        
        # Create user using user service
        from app.models.models import UserCreate
        user_create = UserCreate(
            firebase_uid=firebase_user.uid,
            full_name=firebase_user.display_name or "User",
            email=firebase_user.email,
            role=role or "user"
        )
        result = await user_service.create_user(user_create)
        
        print(f"DEBUG: Insert result: {result}")
        
        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user"
            )
        
        # NOTE: Onboarding email will be sent after questionnaire completion
        # not during signup, to ensure user has completed the onboarding form
        
        return {
            "user_id": result.user_id,
            "email": result.email,
            "full_name": result.full_name,
            "is_new_user": True,
            "role": result.role
        }

@router.post("/login")
async def firebase_login(request: Request):
    """Handle Firebase login with ID token"""
    try:
        t0 = time.perf_counter()
        validate_firebase_config()
        
        # Get the ID token from request body
        body = await request.json()
        id_token = body.get("idToken")
        # Accept optional full name from client during login (common when frontend calls Firebase directly)
        request_full_name = (
            body.get("fullName")
            or body.get("full_name")
            or body.get("name")
            or body.get("displayName")
        )
        
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail="ID token is required"
            )
        
        # Verify the Firebase token
        t_verify_start = time.perf_counter()
        firebase_user = await verify_firebase_token(id_token)
        t_verify_end = time.perf_counter()

        # If client provided a name explicitly, prefer that over token's name
        if request_full_name and isinstance(request_full_name, str):
            firebase_user.display_name = request_full_name.strip() or firebase_user.display_name
        
        # Find or create user in our database (no backfill on critical path)
        t_focu_start = time.perf_counter()
        user_data = await find_or_create_user(firebase_user, do_backfill=False)
        t_focu_end = time.perf_counter()
        
        print(f"DEBUG: User data before JWT creation: {user_data}")
        
        # Generate JWT token
        t_token_start = time.perf_counter()
        jwt_token = create_access_token(
            data={"sub": user_data["email"], "full_name": user_data.get("full_name", "")},
            user_id=user_data["user_id"],
            roles=[user_data["role"]] if user_data.get("role") else []
        )
        t_token_end = time.perf_counter()
        
        print(f"DEBUG: JWT token created successfully")
        
        # Background tasks for post-login updates
        try:
            t_bg_start = time.perf_counter()
            # asyncio.create_task(asyncio.to_thread(ensure_minimal_profile, user_data["user_id"], user_data.get("full_name")))  # Commented out - module doesn't exist
            # Backfill name/role after response
            asyncio.create_task(find_or_create_user(firebase_user, role=user_data.get("role", ""), do_backfill=True))
            t_bg_end = time.perf_counter()
        except Exception:
            t_bg_end = time.perf_counter()
            pass

        # Check MFA status for the user
        mfa_status = await mfa_service.check_mfa_status(user_data["user_id"])
        
        response_data = {
            "success": True,
            "token": jwt_token,
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "role": user_data.get("role", ""),
                "is_new_user": user_data["is_new_user"]
            },
            "mfa": {
                "enrolled": mfa_status.get("mfa_enrolled", False),
                "enrolled_factors": mfa_status.get("enrolled_factors", [])
            }
        }
        # Create or retrieve stable per-user session and include session_id in response
        try:
            if Agentv2SessionManager is not None:
                # Non-blocking fallback session id; compute real session in background
                response_data["session_id"] = f"agentv2_{user_data['user_id']}"
                response_data["active_idea"] = None
                try:
                    t_session_start = time.perf_counter()
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                    session_manager = Agentv2SessionManager(redis_url, get_supabase_client())
                    async def _warm_session():
                        try:
                            sess = await asyncio.to_thread(session_manager.get_or_create_session, user_data["user_id"]) 
                            _ = await asyncio.to_thread(session_manager.derive_active_idea, user_data["user_id"], sess.get("session_id"))
                        except Exception:
                            pass
                    asyncio.create_task(_warm_session())
                    t_session_end = time.perf_counter()
                except Exception:
                    t_session_end = time.perf_counter()
                    pass
            else:
                response_data["session_id"] = f"agentv2_{user_data['user_id']}"
                response_data["active_idea"] = None
        except Exception:
            response_data["session_id"] = f"agentv2_{user_data['user_id']}"
            response_data["active_idea"] = None
        
        print(f"DEBUG: Response data: {response_data}")
        
        t_end = time.perf_counter()
        # Log timing summary
        try:
            logger.info(
                "perf firebase_login user_id=%s total_ms=%.1f verify_ms=%.1f focu_ms=%.1f token_ms=%.1f bg_ms=%.1f session_ms=%.1f",
                user_data.get("user_id"),
                (t_end - t0) * 1000.0,
                (t_verify_end - t_verify_start) * 1000.0,
                (t_focu_end - t_focu_start) * 1000.0,
                (t_token_end - t_token_start) * 1000.0,
                (t_bg_end - t_bg_start) * 1000.0 if 't_bg_start' in locals() else 0.0,
                (t_session_end - t_session_start) * 1000.0 if 't_session_start' in locals() else 0.0,
            )
        except Exception:
            pass

        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firebase login error: {str(e)}")

@router.get("/user")
async def get_firebase_user_info_endpoint(jwt_token: str):
    """Get current user information from JWT token"""
    try:
        user_id = get_user_id_from_token(jwt_token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT token"
            )
        
        # Get user data from database
        supabase = get_supabase()
        result = supabase.table("users").select("user_id, email, full_name, created_at").eq("user_id", user_id).execute()
        user_data = result.data
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Ensure minimal profile row exists/backfilled with full name
        try:
            asyncio.create_task(asyncio.to_thread(ensure_minimal_profile, user_id, None))
        except Exception:
            pass

        return {
            "success": True,
            "user": user_data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def firebase_logout():
    """Logout endpoint (client should clear JWT token)"""
    return {
        "success": True,
        "message": "Logged out successfully"
    }

@router.get("/config")
async def get_firebase_config():
    """Get Firebase configuration for frontend"""
    validate_firebase_config()
    
    return {
        "apiKey": FIREBASE_API_KEY,
        "authDomain": FIREBASE_AUTH_DOMAIN,
        "projectId": FIREBASE_PROJECT_ID
    }

@router.post("/forgot-password")
async def forgot_password(request: Request):
    """Handle forgot password request using Firebase REST API"""
    try:
        validate_firebase_config()
        
        body = await request.json()
        email = body.get("email")
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Email is required"
            )
        
        # Use Firebase REST API to send password reset email
        # Firebase Identity Toolkit API endpoint for sending password reset email
        firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
        
        # Set continue URL for redirect after password reset
        # Default to frontend_url + /auth, or use the continueUrl from request if provided
        continue_url = body.get("continueUrl") or format_auth_url()
        
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email,
            "continueUrl": continue_url
        }
        
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(firebase_url, json=payload)
            
            if response.status_code == 200:
                # Firebase successfully sent the password reset email
                return {
                    "success": True,
                    "message": "Password reset email sent successfully. Please check your inbox.",
                    "email": email
                }
            else:
                # Parse Firebase error response
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    
                    # Handle specific Firebase errors
                    if "EMAIL_NOT_FOUND" in error_message:
                        # For security, don't reveal if email exists or not
                        # Return success message anyway
                        return {
                            "success": True,
                            "message": "If an account with this email exists, a password reset email has been sent.",
                            "email": email
                        }
                    elif "TOO_MANY_ATTEMPTS_TRY_LATER" in error_message:
                        raise HTTPException(
                            status_code=429,
                            detail="Too many password reset attempts. Please try again later."
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to send password reset email: {error_message}"
                        )
                except ValueError:
                    # If response is not JSON, use the raw text
                    raise HTTPException(
                        status_code=400,
                        detail=f"Firebase password reset failed: {response.text}"
                    )
                    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Password reset error: {str(e)}"
        )

@router.post("/signup")
async def firebase_signup(request: Request):
    """Handle Firebase signup with ID token"""
    try:
        t0 = time.perf_counter()
        validate_firebase_config()
        
        body = await request.json()
        id_token = body.get("idToken")
        # Force blank role on signup regardless of client-provided value
        role = ""
        # Accept multiple keys for full name from frontend
        full_name = (
            body.get("fullName")
            or body.get("full_name")
            or body.get("name")
            or body.get("displayName")
        )
        
        print(f"DEBUG: Signup request - Role forced to blank")
        print(f"DEBUG: Signup request - Full Name: {full_name}")
        print(f"DEBUG: Full request body: {body}")
        
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail="Firebase ID token is required"
            )
        
        # Verify Firebase token and get user info
        t_verify_start = time.perf_counter()
        firebase_user = await verify_firebase_token(id_token)
        t_verify_end = time.perf_counter()
        
        # Use the full name from request body if provided, otherwise use Firebase display_name
        if full_name and isinstance(full_name, str):
            firebase_user.display_name = full_name.strip() or firebase_user.display_name
        
        # Find or create user in our database (no backfill on critical path)
        t_focu_start = time.perf_counter()
        user_data = await find_or_create_user(firebase_user, role, do_backfill=False)
        t_focu_end = time.perf_counter()
        
        print(f"DEBUG: User data after find_or_create_user: {user_data}")
        
        # Generate JWT token
        t_token_start = time.perf_counter()
        jwt_token = create_access_token(
            data={"sub": user_data["email"], "full_name": user_data.get("full_name", "")},
            user_id=user_data["user_id"],
            roles=[user_data["role"]] if user_data.get("role") else []
        )
        t_token_end = time.perf_counter()
        
        # Background tasks for post-signup updates
        try:
            t_bg_start = time.perf_counter()
            # asyncio.create_task(asyncio.to_thread(ensure_minimal_profile, user_data["user_id"], user_data.get("full_name")))  # Commented out - module doesn't exist
            # Backfill name/role after response if needed
            asyncio.create_task(find_or_create_user(firebase_user, role=role, do_backfill=True))
            t_bg_end = time.perf_counter()
        except Exception:
            t_bg_end = time.perf_counter()
            pass

        # Send welcome email only if this was a new user
        try:
            if user_data.get("is_new_user"):
                # Fire-and-forget welcome email
                import asyncio as _asyncio
                # _asyncio.create_task(send_welcome_email(user_data["email"], user_data.get("full_name")))  # Commented out - module doesn't exist
        except Exception:
            pass

        # Fire-and-forget Klaviyo "Signed Up" event for new users
        try:
            if user_data.get("is_new_user"):
                # klaviyo = get_klaviyo_client()  # Commented out - module doesn't exist
                # Non-blocking: do not await here inside request path; it's okay to await in async since we're in an async function, but to avoid delaying response we'll schedule a task
                # import asyncio as _asyncio
                # _asyncio.create_task(
                #     klaviyo.track_signed_up(
                #         email=user_data["email"],
                #         full_name=user_data.get("full_name"),
                #         user_id=user_data["user_id"],
                #         metadata={"source": "firebase_signup"}
                #     )
                # )
                pass  # Placeholder for commented out code
        except Exception:
            pass

        # Check MFA status for the user
        mfa_status = await mfa_service.check_mfa_status(user_data["user_id"])
        
        response_payload = {
            "success": True,
            "token": jwt_token,
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "role": user_data.get("role", ""),
                "is_new_user": user_data["is_new_user"]
            },
            "mfa": {
                "enrolled": mfa_status.get("mfa_enrolled", False),
                "enrolled_factors": mfa_status.get("enrolled_factors", [])
            },
            "session_id": (lambda: (
                Agentv2SessionManager(redis_url := os.getenv("REDIS_URL", "redis://localhost:6379"), get_supabase_client()).get_or_create_session(user_data["user_id"])  # noqa: E731
            ))()["session_id"] if Agentv2SessionManager is not None else f"agentv2_{user_data['user_id']}",
            "active_idea": (lambda: (
                Agentv2SessionManager(redis_url := os.getenv("REDIS_URL", "redis://localhost:6379"), get_supabase_client()).derive_active_idea(user_id=user_data["user_id"])  # noqa: E731
            ))() if Agentv2SessionManager is not None else None
        }

        t_end = time.perf_counter()
        try:
            logger.info(
                "perf firebase_signup user_id=%s total_ms=%.1f verify_ms=%.1f focu_ms=%.1f token_ms=%.1f bg_ms=%.1f",
                user_data.get("user_id"),
                (t_end - t0) * 1000.0,
                (t_verify_end - t_verify_start) * 1000.0,
                (t_focu_end - t_focu_start) * 1000.0,
                (t_token_end - t_token_start) * 1000.0,
                (t_bg_end - t_bg_start) * 1000.0 if 't_bg_start' in locals() else 0.0,
            )
        except Exception:
            pass

        return response_payload
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup error: {str(e)}")

@router.post("/email-login")
async def firebase_email_login(request: Request):
    """Handle Firebase email/password login with ID token"""
    try:
        validate_firebase_config()
        
        body = await request.json()
        id_token = body.get("idToken")
        # Accept optional full name here as well
        request_full_name = (
            body.get("fullName")
            or body.get("full_name")
            or body.get("name")
            or body.get("displayName")
        )
        
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail="Firebase ID token is required"
            )
        
        # Verify Firebase token and get user info
        firebase_user = await verify_firebase_token(id_token)

        # Prefer client-provided name if present
        if request_full_name and isinstance(request_full_name, str):
            firebase_user.display_name = request_full_name.strip() or firebase_user.display_name
        
        # Find or create user in our database
        user_data = await find_or_create_user(firebase_user)
        
        # Generate JWT token
        jwt_token = create_access_token(
            data={"sub": user_data["email"], "full_name": user_data.get("full_name", "")},
            user_id=user_data["user_id"],
            roles=[user_data["role"]] if user_data.get("role") else []
        )
        
        return {
            "success": True,
            "token": jwt_token,
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "role": user_data.get("role", ""),
                "is_new_user": user_data["is_new_user"]
            },
            "session_id": (lambda: (
                Agentv2SessionManager(redis_url := os.getenv("REDIS_URL", "redis://localhost:6379"), get_supabase_client()).get_or_create_session(user_data["user_id"])  # noqa: E731
            ))()["session_id"] if Agentv2SessionManager is not None else f"agentv2_{user_data['user_id']}",
            "active_idea": (lambda: (
                Agentv2SessionManager(redis_url := os.getenv("REDIS_URL", "redis://localhost:6379"), get_supabase_client()).derive_active_idea(user_id=user_data["user_id"])  # noqa: E731
            ))() if Agentv2SessionManager is not None else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")

@router.put("/update-user-type")
async def update_user_type(request: Request, authorization: str = Header(None)):
    """Update user type and description in the database"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Valid Authorization header with Bearer token is required"
            )
        
        jwt_token = authorization.replace("Bearer ", "")
        
        # Get user_id from JWT token
        user_id = get_user_id_from_token(jwt_token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT token"
            )
        
        # Parse request body
        body = await request.json()
        
        # Validate request data
        try:
            profile_update = UserProfileUpdate(**body)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request data: {str(e)}"
            )
        
        # Verify that the user_id in the request matches the one from JWT token
        if profile_update.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only update your own profile"
            )
        
        # Update user profile in database using Supabase client
        supabase = get_supabase_client()
        
        update_data = {
            "user_type": profile_update.user_type,
            "description": profile_update.description,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        update_op = supabase.table("users").update(update_data).eq("user_id", user_id)
        result = await asyncio.to_thread(update_op.execute)
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        updated_user = result.data[0]
        
        return {
            "success": True,
            "message": "User type and description updated successfully",
            "user": {
                "user_id": updated_user["user_id"],
                "email": updated_user["email"],
                "full_name": updated_user["full_name"],
                "user_type": updated_user["user_type"],
                "description": updated_user["description"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile update error: {str(e)}") 

@router.put("/update-role-followup")
async def update_role_followup(request: Request, authorization: str = Header(None)):
    """Update the user's role and/or follow_up fields in the users table"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Valid Authorization header with Bearer token is required"
            )

        jwt_token = authorization.replace("Bearer ", "")

        # Get user_id from JWT token
        user_id = get_user_id_from_token(jwt_token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT token"
            )

        # Parse and validate request body
        body = await request.json()
        try:
            payload = UpdateRoleFollowUpRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

        if payload.role is None and payload.follow_up is None:
            raise HTTPException(status_code=400, detail="Provide at least one of 'role' or 'follow_up'")

        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }

        # Validate and set role if provided
        if payload.role is not None:
            role_value = payload.role.strip()
            if role_value and role_value not in ALLOWED_USER_ROLES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid role. Allowed roles: {', '.join(ALLOWED_USER_ROLES)}"
                )
            update_data["role"] = role_value

        # Set follow_up if provided (free text)
        if payload.follow_up is not None:
            update_data["follow_up"] = payload.follow_up

        supabase = get_supabase_client()
        update_op = supabase.table("users").update(update_data).eq("user_id", user_id)
        result = await asyncio.to_thread(update_op.execute)

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        updated_user = result.data[0]

        # Generate a fresh JWT that reflects the updated role
        jwt_token = create_access_token(
            data={
                "sub": updated_user.get("email"),
                "full_name": updated_user.get("full_name", "")
            },
            user_id=updated_user["user_id"],
            roles=[updated_user.get("role")] if updated_user.get("role") else []
        )

        return {
            "success": True,
            "message": "User role/follow_up updated successfully",
            "token": jwt_token,
            "user": {
                "user_id": updated_user["user_id"],
                "email": updated_user.get("email"),
                "full_name": updated_user.get("full_name"),
                "role": updated_user.get("role", ""),
                "follow_up": updated_user.get("follow_up")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

@router.post("/login-with-mfa")
async def firebase_login_with_mfa(request: Request):
    """Handle Firebase login with MFA verification"""
    try:
        validate_firebase_config()
        
        body = await request.json()
        id_token = body.get("idToken")
        mfa_response = body.get("mfaResponse")  # MFA response from client
        
        if not id_token:
            raise HTTPException(
                status_code=400,
                detail="ID token is required"
            )
        
        # Verify the Firebase token
        firebase_user = await verify_firebase_token(id_token)
        
        # Find or create user in our database
        user_data = await find_or_create_user(firebase_user, do_backfill=False)
        
        # Check if user has MFA enrolled
        mfa_status = await mfa_service.check_mfa_status(user_data["user_id"])
        
        if mfa_status.get("mfa_enrolled", False):
            # User has MFA enrolled, verify MFA response
            if not mfa_response:
                return {
                    "success": False,
                    "mfa_required": True,
                    "message": "MFA verification required",
                    "enrolled_factors": mfa_status.get("enrolled_factors", [])
                }
            
            # Here you would verify the MFA response with Firebase
            # For now, we'll assume it's valid if provided
            # In production, you should verify the MFA response properly
        
        # Generate JWT token
        jwt_token = create_access_token(
            data={"sub": user_data["email"], "full_name": user_data.get("full_name", "")},
            user_id=user_data["user_id"],
            roles=[user_data["role"]] if user_data.get("role") else []
        )
        
        return {
            "success": True,
            "token": jwt_token,
            "user": {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "role": user_data.get("role", ""),
                "is_new_user": user_data["is_new_user"]
            },
            "mfa": {
                "enrolled": mfa_status.get("mfa_enrolled", False),
                "enrolled_factors": mfa_status.get("enrolled_factors", [])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firebase login with MFA error: {str(e)}")

@router.get("/test-role")
async def test_role_functionality():
    """Test endpoint to verify role functionality"""
    return {
        "message": "Role functionality is working",
        "available_roles": ["user", "admin", "moderator", "premium"],
        "default_role": "",
        "endpoint": "/auth/firebase/signup",
        "payload_example": {
            "idToken": "firebase_id_token_here",
            "role": "admin",  # Optional, defaults to blank
            "fullName": "John Doe"  # Optional, will use Firebase token name if not provided
        }
    }

