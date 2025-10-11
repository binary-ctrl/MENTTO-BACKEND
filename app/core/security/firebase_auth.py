import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Try to use local credentials file first
        credentials_file = "/Users/vikaskamwal/Downloads/mentto-project/mento-backend/credentials.json"
        if os.path.exists(credentials_file):
            # Check if it's a service account file
            with open(credentials_file, 'r') as f:
                cred_data = f.read()
                if '"type": "service_account"' in cred_data:
                    cred = credentials.Certificate(credentials_file)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized with local service account file")
                    return
                else:
                    logger.warning("Local credentials.json is not a service account file")
        
        # Try to use service account credentials from environment variables
        if (hasattr(settings, 'firebase_private_key') and 
            settings.firebase_private_key and 
            settings.firebase_private_key != "your_firebase_private_key" and
            settings.firebase_private_key_id and
            settings.firebase_client_email and
            settings.firebase_client_id):
            # Create credentials from environment variables
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key_id": settings.firebase_private_key_id,
                "private_key": settings.firebase_private_key.replace('\\n', '\n'),
                "client_email": settings.firebase_client_email,
                "client_id": settings.firebase_client_id,
                "auth_uri": settings.firebase_auth_uri,
                "token_uri": settings.firebase_token_uri,
            })
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with service account credentials")
        else:
            # Use Application Default Credentials
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with Application Default Credentials")
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        # Don't raise the exception, just log it and continue
        logger.warning("Firebase initialization failed, but continuing without Firebase Admin SDK")

def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token and return user info"""
    try:
        # Try Firebase Admin SDK first
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "email_verified": decoded_token.get("email_verified", False)
        }
    except Exception as e:
        logger.warning(f"Firebase Admin SDK verification failed: {e}")
        # Fallback to Google OAuth token verification
        return verify_google_oauth_token(token)

def verify_google_oauth_token(token: str) -> dict:
    """Verify Google OAuth token as fallback"""
    import httpx
    import asyncio
    
    try:
        # Use Google's tokeninfo endpoint
        async def verify_token():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?access_token={token}"
                )
                if response.status_code == 200:
                    token_info = response.json()
                    return {
                        "uid": token_info.get("sub"),
                        "email": token_info.get("email"),
                        "name": token_info.get("name"),
                        "picture": token_info.get("picture"),
                        "email_verified": token_info.get("email_verified", False)
                    }
                else:
                    raise ValueError("Invalid token")
        
        # Run the async function
        return asyncio.run(verify_token())
        
    except Exception as e:
        logger.error(f"Failed to verify Google OAuth token: {e}")
        raise ValueError("Invalid token")

def get_firebase_user(uid: str) -> dict:
    """Get user information from Firebase"""
    try:
        user = auth.get_user(uid)
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "email_verified": user.email_verified,
            "disabled": user.disabled
        }
    except Exception as e:
        logger.error(f"Failed to get Firebase user: {e}")
        raise ValueError("User not found")

# Initialize Firebase when module is imported
try:
    initialize_firebase()
except Exception as e:
    logger.warning(f"Firebase initialization failed: {e}")
