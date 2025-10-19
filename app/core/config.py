from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field, AliasChoices
from typing import Optional, List
import os


class Settings(BaseSettings):
    # Pydantic v2 settings config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    # Supabase Configuration
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    
    # Firebase Configuration
    firebase_project_id: str
    firebase_private_key_id: Optional[str] = None
    firebase_private_key: Optional[str] = None
    firebase_client_email: Optional[str] = None
    firebase_client_id: Optional[str] = None
    firebase_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    firebase_token_uri: str = "https://oauth2.googleapis.com/token"
    
    # Google OAuth Configuration (server-side)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None  # e.g., http://localhost:8000/auth/google/callback
    google_calendar_redirect_uri: Optional[str] = None  # e.g., http://localhost:8001/calendar/callback
    
    # Frontend URL for post-auth redirect
    frontend_url: str = "http://localhost:5173"

    # Firebase Web API key for Identity Toolkit (email/password signup)
    firebase_api_key: Optional[str] = None
    
    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 43200  # 30 days
    
    # Email Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    from_email: Optional[str] = None
    
    # Razorpay Configuration
    razor_pay_key_id: Optional[str] = None
    razor_pay_key_seceret: Optional[str] = None  # Note: keeping the typo to match .env file
    # Support both RAZORPAY_WEBHOOK_SECRET and legacy RAZOR_PAY_WEBHOOK_SECRET
    razorpay_webhook_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("RAZORPAY_WEBHOOK_SECRET", "RAZOR_PAY_WEBHOOK_SECRET"),
    )
    
    # WhatsApp (WATI) Configuration
    wati_base_url: Optional[str] = None
    # Accept alternative env var names for convenience
    wati_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WATI_API_KEY", "WAITIO"),
    )
    enable_wati_notifications: bool = False
    
    # Storage Configuration
    storage_bucket_name: str = "profile_picture"
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_file_types: List[str] = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    
    # App Configuration
    app_name: str = "Mentto Backend"
    debug: bool = True
    
    @field_validator('smtp_use_tls', 'debug', 'enable_wati_notifications', mode='before')
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return bool(v)
    
    # Note: In Pydantic v2, we use model_config above instead of inner Config class


# Create settings instance
settings = Settings()
