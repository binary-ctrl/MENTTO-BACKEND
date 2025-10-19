"""
Authentication API routes
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
import httpx
import secrets
import logging
from typing import Optional

from app.core.config import settings
from app.core.security.firebase_auth import verify_firebase_token
from app.core.security.jwt_auth import create_user_token
from app.core.security.auth_dependencies import get_current_user
from app.models.models import (
    FirebaseTokenRequest, TokenResponse, UserResponse,
    EmailPasswordSignupRequest, EmailPasswordLoginRequest
)
from app.services.user.services import user_service

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

def _validate_google_oauth_config():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    if not settings.google_redirect_uri:
        raise HTTPException(status_code=500, detail="Missing google_redirect_uri")

@router.post("/signup", response_model=TokenResponse)
async def signup(request: FirebaseTokenRequest):
    """Sign up user with Firebase token"""
    try:
        # Verify Firebase token
        firebase_user = verify_firebase_token(request.firebase_token)
        
        # Check if user already exists
        existing_user = await user_service.get_user_by_firebase_uid(firebase_user["uid"])
        
        if existing_user:
            # User exists, create new token
            token = create_user_token(
                user_id=existing_user.user_id,
                email=existing_user.email,
                name=existing_user.full_name,
                role=existing_user.role,
                firebase_uid=firebase_user["uid"]
            )
            return TokenResponse(access_token=token, user=existing_user)
        
        # Create new user
        from app.models.models import UserCreate
        user_data = UserCreate(
            firebase_uid=firebase_user["uid"],
            full_name=firebase_user.get("name", ""),
            email=firebase_user["email"],
            role=request.role
        )
        
        new_user = await user_service.create_user(user_data)
        
        # NOTE: Onboarding email will be sent after questionnaire completion
        # not during signup, to ensure user has completed the onboarding form
        
        # Create JWT token
        token = create_user_token(
            user_id=new_user.user_id,
            email=new_user.email,
            name=new_user.full_name,
            role=new_user.role,
            firebase_uid=firebase_user["uid"]
        )
        
        return TokenResponse(access_token=token, user=new_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )

@router.post("/email-login", response_model=TokenResponse)
async def email_password_login(login_data: EmailPasswordLoginRequest):
    """Login with email and password using Firebase REST API"""
    try:
        # Use Firebase REST API to sign in with email/password
        firebase_api_key = settings.firebase_api_key
        if not firebase_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase API key not configured"
            )

        # Firebase REST API endpoint for email/password sign in
        firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"
        
        payload = {
            "email": login_data.email,
            "password": login_data.password,
            "returnSecureToken": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(firebase_url, json=payload)
            
            if response.status_code != 200:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Login failed")
                
                if "INVALID_PASSWORD" in error_message or "EMAIL_NOT_FOUND" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
                elif "USER_DISABLED" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User account has been disabled"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Login failed: {error_message}"
                    )

            firebase_data = response.json()
            firebase_uid = firebase_data["localId"]
            firebase_id_token = firebase_data["idToken"]

        # Find user in our database by Firebase UID
        user = await user_service.get_user_by_firebase_uid(firebase_uid)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please sign up first."
            )

        # Create our application JWT token
        token = create_user_token(user.user_id, user.email, user.full_name, user.role, firebase_uid)
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=user
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/email-signup", response_model=TokenResponse)
async def email_password_signup(payload: EmailPasswordSignupRequest):
    """Sign up a user by creating credentials in Firebase and storing email in Supabase."""
    if not settings.firebase_api_key:
        raise HTTPException(status_code=500, detail="FIREBASE_API_KEY not configured")

    # 1) Create user in Firebase (email/password)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            fb_resp = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={settings.firebase_api_key}",
                json={
                    "email": payload.email,
                    "password": payload.password,
                    "returnSecureToken": True,
                },
            )
        if fb_resp.status_code != 200:
            # Parse Firebase error response
            try:
                error_data = fb_resp.json()
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                
                # Handle specific Firebase errors gracefully
                if "EMAIL_EXISTS" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An account with this email already exists. Please try logging in instead."
                    )
                elif "WEAK_PASSWORD" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password is too weak. Please choose a stronger password."
                    )
                elif "INVALID_EMAIL" in error_message:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid email address format."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Registration failed: {error_message}"
                    )
            except ValueError:
                # If response is not JSON, use the raw text
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Firebase signUp failed: {fb_resp.text}"
                )
        
        fb_data = fb_resp.json()
        firebase_uid = fb_data.get("localId")
        if not firebase_uid:
            raise HTTPException(status_code=400, detail="Firebase did not return localId")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firebase signUp error: {e}")

    # 2) Store email in Supabase (no password)
    try:
        # Reuse existing creation flow by adapting to UserCreate
        from app.models.models import UserCreate
        user_data = UserCreate(
            firebase_uid=firebase_uid,
            full_name=payload.full_name or payload.email.split("@")[0],
            email=payload.email,
            role=payload.role,
        )
        app_user = await user_service.create_user(user_data)
        
        # NOTE: Onboarding email will be sent after questionnaire completion
        # not during signup, to ensure user has completed the onboarding form
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase insert failed: {e}")

    # 3) Issue app JWT
    token = create_user_token(
        user_id=app_user.user_id,
        email=app_user.email,
        name=app_user.full_name,
        role=app_user.role,
        firebase_uid=firebase_uid,
    )
    return TokenResponse(access_token=token, user=app_user)

@router.post("/verify", response_model=TokenResponse)
async def verify_token_endpoint(request: FirebaseTokenRequest):
    """Verify Firebase token and return JWT token"""
    try:
        # Verify Firebase token
        firebase_user = verify_firebase_token(request.firebase_token)
        
        # Get user from database
        user = await user_service.get_user_by_firebase_uid(firebase_user["uid"])
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please sign up first."
            )
        
        # Create JWT token
        token = create_user_token(
            user_id=user.user_id,
            email=user.email,
            name=user.full_name,
            role=user.role,
            firebase_uid=firebase_user["uid"]
        )
        
        return TokenResponse(access_token=token, user=user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify token"
        )

@router.get("/google/signup")
async def google_signup(role: str = "mentee"):
    """Initiate Google OAuth signup flow for new users with role selection."""
    _validate_google_oauth_config()

    # Validate role parameter
    if role not in ["mentee", "mentor", "parent"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'mentee', 'mentor' or 'parent'"
        )

    state = secrets.token_urlsafe(32)
    # Store state with signup intent and role
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": f"signup_{role}_{state}",  # Include role in state
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")

@router.get("/google/signin")
async def google_signin():
    """Initiate Google OAuth signin flow for existing users."""
    _validate_google_oauth_config()

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": f"signin_{state}",  # Prefix to indicate signin intent
        "access_type": "offline",
        "prompt": "select_account",  # Show account selector for signin
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")

@router.get("/google/callback")
async def google_callback(code: str, state: Optional[str] = None, error: Optional[str] = None):
    """Handle Google OAuth callback for both signup and signin flows."""
    _validate_google_oauth_config()
    
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    # Determine if this is signup, signin, or calendar OAuth based on state
    is_signup = state and state.startswith("signup_")
    is_signin = state and state.startswith("signin_")
    is_calendar = state and not (is_signup or is_signin)  # Calendar OAuth uses user_id as state
    
    # If this is a calendar OAuth callback, redirect to calendar callback
    if is_calendar:
        # Redirect to calendar callback with the same parameters
        calendar_callback_url = f"/calendar/callback?code={code}&state={state}"
        if error:
            calendar_callback_url += f"&error={error}"
        return RedirectResponse(url=calendar_callback_url)
    
    # Extract role from state if it's a signup flow
    user_role = "mentee"  # default role
    if is_signup and "_" in state:
        parts = state.split("_")
        if len(parts) >= 3:  # signup_role_randomstring
            user_role = parts[1]  # Extract role from state
    
    if not (is_signup or is_signin):
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")

    # Debug: Print the values being used
    print(f"DEBUG - Using client_id: {settings.google_client_id}")
    print(f"DEBUG - Using client_secret: {settings.google_client_secret[:10]}...")
    print(f"DEBUG - Using redirect_uri: {settings.google_redirect_uri}")
    print(f"DEBUG - Using code: {code[:20]}...")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_redirect_uri,
        }
        print(f"DEBUG - Token data: {token_data}")
        token_resp = await client.post(GOOGLE_TOKEN_URL, data=token_data)
        print(f"DEBUG - Response status: {token_resp.status_code}")
        print(f"DEBUG - Response text: {token_resp.text}")
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_resp.text}")
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token from Google")

        # Fetch userinfo
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to fetch userinfo: {userinfo_resp.text}")
        google_user = userinfo_resp.json()

    email = google_user.get("email")
    full_name = google_user.get("name", "")
    google_id = google_user.get("id")  # Google user id
    if not email or not google_id:
        raise HTTPException(status_code=400, detail="Google user info incomplete")

    # Check if user exists
    existing_user = await user_service.get_user_by_email(email)
    
    if is_signup:
        # Signup flow - create new user or return existing user
        if existing_user:
            # User already exists, treat as signin
            app_user = existing_user
            is_new_user = False
        else:
            # Create new user with the selected role
            from app.models.models import UserCreate, UserRole
            if user_role == "mentee":
                role_enum = UserRole.MENTEE
            elif user_role == "mentor":
                role_enum = UserRole.MENTOR
            elif user_role == "parent":
                role_enum = UserRole.PARENT
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role. Must be 'mentee', 'mentor' or 'parent'"
                )
            user_data = UserCreate(
                firebase_uid=google_id,  # Use Google ID as firebase_uid
                full_name=full_name,
                email=email,
                role=role_enum,  # Use the role from the signup flow
            )
            app_user = await user_service.create_user(user_data)
            is_new_user = True
            
            # NOTE: Onboarding email will be sent after questionnaire completion
            # not during signup, to ensure user has completed the onboarding form
            
    elif is_signin:
        # Signin flow - user must exist
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please sign up first."
            )
        app_user = existing_user
        is_new_user = False
    else:
        raise HTTPException(status_code=400, detail="Invalid OAuth flow")

    # Issue our app JWT
    token = create_user_token(
        user_id=app_user.user_id,
        email=app_user.email,
        name=app_user.full_name,
        role=app_user.role,
        firebase_uid=google_id,
    )

    # Redirect to frontend with token and user info based on role and flow
    frontend = settings.frontend_url or "http://localhost:8080"
    
    if is_signup and is_new_user:
        # Role-based redirects for new users
        if user_role == "mentee":
            redirect_url = f"{frontend}/onboarding/mentee?token={token}"
        elif user_role == "mentor":
            redirect_url = f"{frontend}/dashboard/mentor?token={token}"
        else:
            # Fallback to default frontend URL
            redirect_url = f"{frontend}/auth/callback?token={token}&is_new_user={is_new_user}&flow=signup"
    else:
        # For signin or existing users, redirect to default callback
        redirect_url = f"{frontend}/auth/callback?token={token}&is_new_user={is_new_user}&flow={'signup' if is_signup else 'signin'}"
    
    return RedirectResponse(url=redirect_url)

@router.post("/google/verify", response_model=TokenResponse)
async def google_verify_token(request: FirebaseTokenRequest):
    """Verify Google OAuth token and return JWT token (for direct token verification)"""
    try:
        # Verify the Google OAuth token
        firebase_user = verify_firebase_token(request.firebase_token)
        
        # Get user from database by firebase_uid (which is Google ID in this case)
        user = await user_service.get_user_by_firebase_uid(firebase_user["uid"])
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please sign up first."
            )
        
        # Create JWT token
        token = create_user_token(
            user_id=user.user_id,
            email=user.email,
            name=user.full_name,
            role=user.role,
            firebase_uid=firebase_user["uid"]
        )
        
        return TokenResponse(access_token=token, user=user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify Google token"
        )

@router.get("/google/user-info")
async def get_google_user_info(current_user = Depends(get_current_user)):
    """Get current user information after Google OAuth authentication"""
    try:
        return {
            "user_id": current_user.user_id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "auth_provider": "google"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )