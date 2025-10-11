"""
Google OAuth 2.0 Implementation for FastAPI
Handles Google OAuth flow with JWT token generation
"""

import os
import secrets
import random
import httpx
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import json

from app.core.config import settings
from app.core.security import create_access_token, get_user_id_from_token
from app.core.database import execute_read_query, execute_write_query

router = APIRouter(prefix="/auth/google", tags=["google_oauth"])

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

class GoogleUserInfo(BaseModel):
    id: str
    email: str
    verified_email: bool
    name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None

def generate_state() -> str:
    """Generate a random state parameter for CSRF protection"""
    return secrets.token_urlsafe(32)

def validate_google_config():
    """Validate that Google OAuth configuration is complete"""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500, 
            detail="Google OAuth not configured: GOOGLE_CLIENT_ID missing"
        )
    if not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500, 
            detail="Google OAuth not configured: GOOGLE_CLIENT_SECRET missing"
        )

async def get_google_user_info(access_token: str) -> GoogleUserInfo:
    """Fetch user information from Google using access token"""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch user info from Google: {response.text}"
            )
        
        user_data = response.json()
        return GoogleUserInfo(**user_data)

async def find_or_create_user(google_user: GoogleUserInfo) -> Dict[str, Any]:
    """Find existing user by Google email or create new user"""
    
    # Check if user exists by email
    query = "SELECT user_id, email, full_name FROM users WHERE email = %s"
    existing_user = execute_read_query(query, (google_user.email,))
    
    if existing_user:
        # User exists, return existing user data
        user_data = existing_user[0]
        return {
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "is_new_user": False
        }
    else:
        # Create new user with your schema
        user_id = str(random.randint(10**9, 10**10 - 1))  # Generate 10-digit user ID that doesn't start with 0
        insert_query = """
            INSERT INTO users (user_id, email, full_name, created_at, updated_at, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id, email, full_name
        """
        result = execute_write_query(
            insert_query,
            (user_id, google_user.email, google_user.name, datetime.utcnow(), datetime.utcnow(), "")
        )
        
        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user"
            )
        
        return {
            "user_id": user_id,
            "email": google_user.email,
            "full_name": google_user.name,
            "is_new_user": True
        }

@router.get("/login")
async def google_login(request: Request):
    """Initiate Google OAuth login flow"""
    try:
        validate_google_config()
        
        # Generate state parameter for CSRF protection
        state = generate_state()
        
        # Store state in session or cache (for demo, we'll use a simple approach)
        # In production, use Redis or database to store state
        request.session["oauth_state"] = state
        
        # Build Google OAuth URL
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        # Construct the authorization URL
        auth_url = f"{GOOGLE_AUTH_URL}?"
        auth_url += "&".join([f"{k}={v}" for k, v in params.items()])
        
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    error: Optional[str] = None
):
    """Handle Google OAuth callback"""
    try:
        validate_google_config()
        
        # Check for OAuth errors
        if error:
            raise HTTPException(
                status_code=400,
                detail=f"Google OAuth error: {error}"
            )
        
        # Validate state parameter (CSRF protection)
        stored_state = request.session.get("oauth_state")
        if not stored_state or stored_state != state:
            raise HTTPException(
                status_code=400,
                detail="Invalid state parameter"
            )
        
        # Exchange authorization code for tokens
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI
            }
            
            response = await client.post(GOOGLE_TOKEN_URL, data=token_data)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to exchange code for tokens: {response.text}"
                )
            
            tokens = response.json()
            access_token = tokens.get("access_token")
            
            if not access_token:
                raise HTTPException(
                    status_code=400,
                    detail="No access token received from Google"
                )
        
        # Get user information from Google
        google_user = await get_google_user_info(access_token)
        
        # Find or create user in our database
        user_data = await find_or_create_user(google_user)
        
        # Get user role from database
        user_role = user_data.get("role", "")
        user_roles = [user_role] if user_role else []
        
        # Generate JWT token
        jwt_token = create_access_token(
            data={"sub": user_data["email"], "full_name": user_data.get("full_name", "")},
            user_id=user_data["user_id"],
            roles=user_roles
        )
        
        # Profile creation handled in user creation above

        # Clear the state from session
        if "oauth_state" in request.session:
            del request.session["oauth_state"]
        
        # Redirect to frontend with JWT token
        # In production, you might want to use secure cookies instead
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}&is_new_user={user_data['is_new_user']}"
        
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback error: {str(e)}")

@router.get("/user")
async def get_google_user_info_endpoint(jwt_token: str):
    """Get current user information from JWT token"""
    try:
        user_id = get_user_id_from_token(jwt_token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT token"
            )
        
        # Get user data from database
        query = "SELECT user_id, email, full_name, created_at FROM users WHERE user_id = %s"
        user_data = execute_read_query(query, (user_id,))
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        return {
            "success": True,
            "user": user_data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def google_logout():
    """Logout endpoint (client should clear JWT token)"""
    return {
        "success": True,
        "message": "Logged out successfully"
    } 