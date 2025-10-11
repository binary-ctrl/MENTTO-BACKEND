"""
MFA Schemas for Firebase SMS and Email Multi-Factor Authentication
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import re

class MFAEnrollRequest(BaseModel):
    """Request schema for enrolling SMS MFA"""
    phone_number: str = Field(..., description="Phone number in E.164 format (e.g., +1234567890)")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        # Basic E.164 format validation
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +1234567890)')
        return v

class MFAEmailEnrollRequest(BaseModel):
    """Request schema for enrolling Email MFA"""
    email: str = Field(..., description="Email address for MFA")
    
    @validator('email')
    def validate_email(cls, v):
        # Basic email format validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('Invalid email format')
        return v

class MFAVerifyRequest(BaseModel):
    """Request schema for verifying SMS MFA enrollment"""
    verification_code: str = Field(..., description="SMS verification code", min_length=6, max_length=6)
    session_info: str = Field(..., description="Session info from enrollment process")

class MFAEmailVerifyRequest(BaseModel):
    """Request schema for verifying Email MFA enrollment"""
    verification_code: str = Field(..., description="Email verification code", min_length=6, max_length=6)
    email: str = Field(..., description="Email address used for MFA")

class MFASignInRequest(BaseModel):
    """Request schema for MFA sign-in"""
    mfa_response: str = Field(..., description="MFA response from client")
    session_info: str = Field(..., description="Session info for MFA challenge")

class MFAStatusResponse(BaseModel):
    """Response schema for MFA status"""
    mfa_enrolled: bool
    enrolled_factors: List[Dict[str, Any]] = []
    message: Optional[str] = None

class MFAEnrollResponse(BaseModel):
    """Response schema for MFA enrollment"""
    success: bool
    message: str
    session_info: Optional[str] = None
    phone_number: Optional[str] = None

class MFAEmailEnrollResponse(BaseModel):
    """Response schema for Email MFA enrollment"""
    success: bool
    message: str
    email: Optional[str] = None
    mfa_type: str = "email"

class MFAVerifyResponse(BaseModel):
    """Response schema for MFA verification"""
    success: bool
    message: str
    mfa_enrolled: bool

class MFAEmailVerifyResponse(BaseModel):
    """Response schema for Email MFA verification"""
    success: bool
    message: str
    mfa_enrolled: bool
    mfa_type: str = "email"

class MFASignInResponse(BaseModel):
    """Response schema for MFA sign-in"""
    mfa_required: bool
    enrolled_factors: List[Dict[str, Any]] = []
    message: Optional[str] = None

class MFADisableResponse(BaseModel):
    """Response schema for disabling MFA"""
    success: bool
    message: str
    mfa_enrolled: bool

class MFAChallengeRequest(BaseModel):
    """Request schema for MFA challenge"""
    user_id: str = Field(..., description="User ID")
    factor_uid: Optional[str] = Field(None, description="Specific MFA factor UID to challenge")

class MFAChallengeResponse(BaseModel):
    """Response schema for MFA challenge"""
    challenge_id: str
    session_info: str
    phone_number: Optional[str] = None
    message: str
