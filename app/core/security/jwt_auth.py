from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None, user_id: Optional[str] = None, roles: Optional[list] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    # Add user_id and roles if provided
    if user_id:
        to_encode["user_id"] = user_id
    if roles:
        to_encode["roles"] = roles
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        return None

def create_user_token(user_id: str, email: str, name: str, role: str, firebase_uid: str) -> str:
    """Create JWT token for authenticated user"""
    token_data = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "firebase_uid": firebase_uid,
        "sub": user_id
    }
    return create_access_token(token_data)

def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token"""
    try:
        payload = verify_token(token)
        if payload:
            return payload.get("user_id") or payload.get("sub")
        return None
    except Exception as e:
        logger.error(f"Error extracting user ID from token: {e}")
        return None
