"""
MFA Routes for Firebase SMS and Email Multi-Factor Authentication
"""

import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional

from app.services.auth.mfa_service import mfa_service
from app.core.security import get_user_id_from_token
from app.api.auth.mfa_schemas import (
    MFAEnrollRequest,
    MFAEnrollResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
    MFAEmailEnrollRequest,
    MFAEmailEnrollResponse,
    MFAEmailVerifyRequest,
    MFAEmailVerifyResponse,
    MFAStatusResponse,
    MFADisableResponse,
    MFAChallengeRequest,
    MFAChallengeResponse,
    MFASignInRequest,
    MFASignInResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])

async def get_current_user_id(authorization: str = Header(None)) -> str:
    """Dependency to get current user ID from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Valid Authorization header with Bearer token is required"
        )
    
    jwt_token = authorization.replace("Bearer ", "")
    user_id = get_user_id_from_token(jwt_token)
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid JWT token"
        )
    
    return user_id

@router.post("/enroll", response_model=MFAEnrollResponse)
async def enroll_sms_mfa(
    request: MFAEnrollRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Enroll user for SMS Multi-Factor Authentication
    
    This endpoint initiates the SMS MFA enrollment process by sending
    a verification code to the provided phone number.
    """
    try:
        result = await mfa_service.enroll_sms_mfa(user_id, request.phone_number)
        
        return MFAEnrollResponse(
            success=result['success'],
            message=result['message'],
            session_info=result.get('session_info'),
            phone_number=result.get('phone_number')
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error enrolling SMS MFA: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/verify", response_model=MFAVerifyResponse)
async def verify_sms_mfa(
    request: MFAVerifyRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Verify SMS MFA enrollment
    
    This endpoint completes the SMS MFA enrollment process by verifying
    the SMS code sent during enrollment.
    """
    try:
        result = await mfa_service.verify_sms_mfa(
            user_id, 
            request.verification_code, 
            request.session_info
        )
        
        return MFAVerifyResponse(
            success=result['success'],
            message=result['message'],
            mfa_enrolled=result['mfa_enrolled']
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying SMS MFA: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/enroll-email", response_model=MFAEmailEnrollResponse)
async def enroll_email_mfa(
    request: MFAEmailEnrollRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Enroll user for Email Multi-Factor Authentication
    
    This endpoint initiates the Email MFA enrollment process by sending
    a verification code to the provided email address.
    """
    try:
        result = await mfa_service.enroll_email_mfa(user_id, request.email)
        
        return MFAEmailEnrollResponse(
            success=result['success'],
            message=result['message'],
            email=result.get('email'),
            mfa_type=result.get('mfa_type', 'email')
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error enrolling Email MFA: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/verify-email", response_model=MFAEmailVerifyResponse)
async def verify_email_mfa(
    request: MFAEmailVerifyRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Verify Email MFA enrollment
    
    This endpoint completes the Email MFA enrollment process by verifying
    the email code sent during enrollment.
    """
    try:
        result = await mfa_service.verify_email_mfa(
            user_id, 
            request.verification_code, 
            request.email
        )
        
        return MFAEmailVerifyResponse(
            success=result['success'],
            message=result['message'],
            mfa_enrolled=result['mfa_enrolled'],
            mfa_type=result.get('mfa_type', 'email')
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying Email MFA: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(user_id: str = Depends(get_current_user_id)):
    """
    Get user's MFA enrollment status
    
    Returns information about the user's current MFA enrollment status
    and enrolled factors.
    """
    try:
        result = await mfa_service.check_mfa_status(user_id)
        
        return MFAStatusResponse(
            mfa_enrolled=result['mfa_enrolled'],
            enrolled_factors=result.get('enrolled_factors', []),
            message=result.get('message')
        )
        
    except Exception as e:
        logger.error(f"Error getting MFA status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/disable", response_model=MFADisableResponse)
async def disable_mfa(user_id: str = Depends(get_current_user_id)):
    """
    Disable MFA for the current user
    
    This endpoint removes all MFA factors for the user and disables
    multi-factor authentication.
    """
    try:
        result = await mfa_service.disable_mfa(user_id)
        
        return MFADisableResponse(
            success=result['success'],
            message=result['message'],
            mfa_enrolled=result['mfa_enrolled']
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error disabling MFA: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/challenge", response_model=MFAChallengeResponse)
async def initiate_mfa_challenge(
    request: MFAChallengeRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Initiate MFA challenge for sign-in
    
    This endpoint starts the MFA challenge process during sign-in
    when the user has MFA enrolled.
    """
    try:
        # Verify the user_id in the request matches the authenticated user
        if request.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only initiate MFA challenge for yourself"
            )
        
        result = await mfa_service.initiate_mfa_signin(user_id)
        
        if not result['mfa_required']:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'MFA is not required for this user')
            )
        
        # For SMS MFA, we need to generate a challenge
        # This is typically handled by the client-side Firebase SDK
        # We'll return the enrolled factors for the client to handle
        return MFAChallengeResponse(
            challenge_id="sms_challenge",  # This would be generated by Firebase
            session_info="",  # This would be provided by Firebase
            phone_number=result['enrolled_factors'][0].get('phone_number') if result['enrolled_factors'] else None,
            message="MFA challenge initiated. Use client-side Firebase SDK to complete."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating MFA challenge: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/signin", response_model=MFASignInResponse)
async def complete_mfa_signin(
    request: MFASignInRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Complete MFA sign-in process
    
    This endpoint verifies the MFA response during sign-in.
    Note: This is typically handled by the client-side Firebase SDK,
    but we provide this endpoint for server-side verification if needed.
    """
    try:
        # This endpoint is mainly for documentation and potential server-side verification
        # In practice, MFA sign-in is handled by the client-side Firebase SDK
        return MFASignInResponse(
            mfa_required=False,
            message="MFA sign-in should be handled by client-side Firebase SDK"
        )
        
    except Exception as e:
        logger.error(f"Error completing MFA signin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/factors")
async def get_enrolled_factors(user_id: str = Depends(get_current_user_id)):
    """
    Get all enrolled MFA factors for the user
    
    Returns detailed information about all enrolled MFA factors.
    """
    try:
        result = await mfa_service.check_mfa_status(user_id)
        
        return {
            "success": True,
            "mfa_enrolled": result['mfa_enrolled'],
            "enrolled_factors": result.get('enrolled_factors', []),
            "total_factors": len(result.get('enrolled_factors', []))
        }
        
    except Exception as e:
        logger.error(f"Error getting enrolled factors: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
