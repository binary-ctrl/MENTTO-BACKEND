from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.core.security.jwt_auth import verify_token
from app.models.models import TokenData
from app.services.user.services import user_service
import logging

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify JWT token
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
            
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        name: str = payload.get("name")
        role: str = payload.get("role")
        firebase_uid: str = payload.get("firebase_uid")
        
        if user_id is None or email is None:
            raise credentials_exception
            
        return TokenData(
            user_id=user_id,
            email=email,
            name=name,
            role=role,
            firebase_uid=firebase_uid
        )
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception

async def get_current_mentee_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get current user and verify they are a mentee"""
    if current_user.role != "mentee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Mentee role required."
        )
    return current_user

async def get_current_mentor_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Get current user and verify they are a mentor"""
    if current_user.role != "mentor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Mentor role required."
        )
    return current_user

async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[TokenData]:
    """Get current user if token is provided, otherwise return None"""
    if not credentials:
        return None
    
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            return None
            
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        name: str = payload.get("name")
        role: str = payload.get("role")
        firebase_uid: str = payload.get("firebase_uid")
        
        if user_id is None or email is None:
            return None
            
        return TokenData(
            user_id=user_id,
            email=email,
            name=name,
            role=role,
            firebase_uid=firebase_uid
        )
        
    except Exception:
        return None
