from fastapi import APIRouter, HTTPException, Depends, Request, Header, Response
from pydantic import BaseModel
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.redis_client import redis_client
from app.core.security import get_user_id_from_token, create_access_token
from app.core.database import get_user_by_id  # Add this import

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Request/Response Models
class RedirectTokenRequest(BaseModel):
    workspace_id: str

class ExchangeTokenRequest(BaseModel):
    redirect_token: str

class RedirectTokenResponse(BaseModel):
    redirect_token: str

class ExchangeTokenResponse(BaseModel):
    jwt_token: str
    workspace_id: str
    user: dict
    session_id: str
    message: str

@router.post("/create-redirect-token", response_model=RedirectTokenResponse)
async def create_redirect_token(
    request_data: RedirectTokenRequest,
    request: Request,
    authorization: str = Header(...)
):
    """Creates a temporary token for SaaS redirect"""
    try:
        print(f"🔍 Creating redirect token for workspace: {request_data.workspace_id}")
        
        # Check Redis availability first
        if not redis_client.is_available():
            print("❌ Redis not available")
            raise HTTPException(
                status_code=503, 
                detail="Redirect token service is temporarily unavailable. Redis connection failed."
            )
        
        print("✅ Redis is available")
        
        # Validate current user with JWT
        print(f"🔍 Validating JWT token...")
        user_id = get_user_id_from_token(authorization)
        if not user_id:
            print("❌ Invalid or missing JWT token")
            raise HTTPException(status_code=401, detail="Invalid or missing JWT token")
        
        print(f"✅ JWT validated, user_id: {user_id}")
        
        # Generate secure random token
        redirect_token = secrets.token_urlsafe(32)
        print(f"🔧 Generated redirect token: {redirect_token}")
        
        # Extract JWT from Authorization header
        if not authorization.startswith("Bearer "):
            print("❌ Invalid authorization header format")
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        jwt_token = authorization.replace("Bearer ", "")
        print(f"🔧 Extracted JWT token: {jwt_token[:50]}...")
        
        # Store token data in Redis with 5-minute expiry
        token_data = {
            "user_id": str(user_id),
            "workspace_id": request_data.workspace_id,
            "jwt_token": jwt_token,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip_address": request.client.host if request.client else "unknown"
        }
        
        print(f"📝 Token data prepared: {token_data}")
        
        # Store in Redis with 300 seconds (5 minutes) expiry
        redis_key = f"redirect_token:{redirect_token}"
        print(f"💾 Storing in Redis with key: {redis_key}")
        
        success = redis_client.set_with_expiry(
            redis_key,
            token_data,
            300  # 5 minutes
        )
        
        if not success:
            print("❌ Failed to store token in Redis")
            raise HTTPException(
                status_code=500, 
                detail="Failed to store redirect token. Redis service may be unavailable."
            )
        
        print("✅ Token stored in Redis successfully")
        
        # Verify the token was actually stored
        verification_data = redis_client.get(redis_key)
        if verification_data:
            print("✅ Token verification successful - token exists in Redis")
        else:
            print("❌ Token verification failed - token not found in Redis")
            raise HTTPException(
                status_code=500, 
                detail="Token was not stored properly in Redis"
            )
        
        print(f"✅ Redirect token created for user {user_id} and workspace {request_data.workspace_id}")
        return RedirectTokenResponse(redirect_token=redirect_token)
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"❌ Error creating redirect token: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to create redirect token")

@router.post("/exchange-redirect-token", response_model=ExchangeTokenResponse)
async def exchange_redirect_token(
    request_data: ExchangeTokenRequest, 
    request: Request,
    response: Response
):
    """Exchanges temporary redirect token for JWT and workspace info with session management"""
    try:
        # Check Redis availability first
        if not redis_client.is_available():
            raise HTTPException(
                status_code=503, 
                detail="Redirect token service is temporarily unavailable. Redis connection failed."
            )
        
        # Step 1: Verify and get token data from Redis
        token_data = redis_client.get(f"redirect_token:{request_data.redirect_token}")
        
        if not token_data:
            print(f"❌ Invalid redirect token attempt from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(status_code=400, detail="Invalid or expired redirect token")
        
        # Step 2: Delete the redirect token immediately (one-time use)
        redis_client.delete(f"redirect_token:{request_data.redirect_token}")
        
        # Step 3: Validate the original JWT token and create new SaaS token
        try:
            user_id = get_user_id_from_token(f"Bearer {token_data['jwt_token']}")
            if not user_id:
                raise HTTPException(status_code=401, detail="Original token expired or invalid")

            # --- ADD: Fetch user email ---
            user = get_user_by_id(user_id)
            user_email = user["email"] if user and "email" in user else None
            user_full_name = user.get("full_name") if user else None
            if not user_email:
                raise HTTPException(status_code=404, detail="User email not found")
            # --- END ADD ---

            # Create a new JWT token specifically for SaaS
            saas_token = create_access_token(
                data={"sub": user_id, "source": "saas_redirect", "email": user_email, "full_name": user_full_name or ""},
                user_id=user_id,
                roles=["saas_user"]  # Specific role for SaaS access
            )
            
            print(f"✅ Created new SaaS JWT token for user {user_id}")
            
        except Exception as e:
            print(f"❌ Invalid JWT in redirect token: {e}")
            raise HTTPException(status_code=401, detail="Original token expired or invalid")
        
        # Step 4: Create a new session ID
        session_id = secrets.token_urlsafe(32)
        
        # Step 5: Store session data in Redis
        session_data = {
            "user_id": user_id,
            "workspace_id": token_data["workspace_id"],
            "jwt_token": saas_token,  # Store the new SaaS token
            "original_jwt_token": token_data["jwt_token"],  # Keep original for reference
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "token_source": "saas_redirect"
        }
        
        # Store session with 24-hour expiry
        session_expiry = 24 * 60 * 60  # 24 hours in seconds
        success = redis_client.set_with_expiry(
            f"session:{session_id}",
            session_data,
            session_expiry
        )
        
        if not success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to create session. Redis service may be unavailable."
            )
        
        # Step 6: Set secure HTTP-only cookie with session ID
        cookie_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        
        print(f"🍪 Setting cookie: session_id={session_id}")
        print(f"🍪 Cookie expiry: {cookie_expiry}")
        print(f"🍪 Request origin: {request.headers.get('origin', 'unknown')}")
        
        response.set_cookie(
            key="session_id",
            value=session_id,
            expires=cookie_expiry,
            httponly=True,  # Prevents JavaScript access
            secure=False,   # Set to True in production with HTTPS
            samesite="lax", # Use lax for development (works with HTTP)
            path="/",        # Available across the entire domain
            domain=None      # Allow all domains for development
        )
        
        print(f"🍪 Cookie set in response headers: {response.headers.get('set-cookie', 'NOT SET')}")
        
        print(f"✅ Successful token exchange and session creation for user {user_id}")
        print(f"   Session ID: {session_id}")
        print(f"   Workspace: {token_data['workspace_id']}")
        
        # Create user info (you can expand this based on your user model)
        user_info = {
            "id": user_id,
            "user_id": user_id,  # For backward compatibility
            "email": user_email  # Add email here
        }
        
        return ExchangeTokenResponse(
            jwt_token=saas_token,
            workspace_id=token_data["workspace_id"],
            user=user_info,
            session_id=session_id,
            message="Session created successfully"
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"❌ Error exchanging redirect token: {e}")
        raise HTTPException(status_code=500, detail="Failed to exchange redirect token")

# New endpoint to validate session
@router.get("/validate-session")
async def validate_session(request: Request):
    """Validate session from cookie and return user info"""
    try:
        # Debug: Log all cookies and headers
        print(f"🔍 All cookies received: {request.cookies}")
        print(f"🔍 All headers: {dict(request.headers)}")
        print(f"🔍 User-Agent: {request.headers.get('user-agent', 'unknown')}")
        print(f"🔍 Origin: {request.headers.get('origin', 'unknown')}")
        print(f"🔍 Referer: {request.headers.get('referer', 'unknown')}")
        print(f"🔍 Host: {request.headers.get('host', 'unknown')}")
        
        # Check Redis availability
        if not redis_client.is_available():
            raise HTTPException(
                status_code=503, 
                detail="Session service is temporarily unavailable. Redis connection failed."
            )
        
        # Get session ID from cookie
        session_id = request.cookies.get("session_id")
        if not session_id:
            print("❌ No session_id cookie found")
            print("🔍 Available cookies:", list(request.cookies.keys()))
            raise HTTPException(status_code=401, detail="No session found")
        
        print(f"✅ Session ID found: {session_id}")
        
        # Get session data from Redis
        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            print(f"❌ Session data not found in Redis for session_id: {session_id}")
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        print(f"✅ Session data found in Redis")
        
        # Update last accessed time
        session_data["last_accessed"] = datetime.now(timezone.utc).isoformat()
        redis_client.set_with_expiry(f"session:{session_id}", session_data, 24 * 60 * 60)
        
        # Return session info
        return {
            "valid": True,
            "user_id": session_data["user_id"],
            "workspace_id": session_data["workspace_id"],
            "created_at": session_data["created_at"],
            "last_accessed": session_data["last_accessed"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error validating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate session")

# OPTIONS endpoint for CORS preflight
@router.options("/validate-session")
async def validate_session_options():
    """Handle CORS preflight for validate-session endpoint"""
    return {"message": "OK"}

# New endpoint to logout and clear session
@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    try:
        # Get session ID from cookie
        session_id = request.cookies.get("session_id")
        
        if session_id and redis_client.is_available():
            # Delete session from Redis
            redis_client.delete(f"session:{session_id}")
            print(f"✅ Session {session_id} deleted from Redis")
        
        # Clear the session cookie
        response.delete_cookie(
            key="session_id",
            path="/",
            httponly=True,
            secure=False,  # Set to True in production
            samesite="lax",
            domain=None
        )
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        print(f"❌ Error during logout: {e}")
        # Still clear the cookie even if Redis fails
        response.delete_cookie(key="session_id", path="/")
        return {"message": "Logged out (with errors)"}

# Alternative endpoints with query parameters (if needed)
@router.post("/create-redirect-token-query")
async def create_redirect_token_query(
    workspace_id: str,
    request: Request,
    authorization: str = Header(...)
):
    """Alternative endpoint using query parameter"""
    request_data = RedirectTokenRequest(workspace_id=workspace_id)
    return await create_redirect_token(request_data, request, authorization)

@router.post("/exchange-redirect-token-query")
async def exchange_redirect_token_query(
    redirect_token: str,
    request: Request,
    response: Response
):
    """Alternative endpoint using query parameter"""
    request_data = ExchangeTokenRequest(redirect_token=redirect_token)
    return await exchange_redirect_token(request_data, request, response) 