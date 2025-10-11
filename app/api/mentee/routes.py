"""
Mentee API routes
"""
from typing import List
import os
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from pydantic import BaseModel

from app.core.security.auth_dependencies import get_current_mentee_user, get_current_user
from app.models.models import (
    MenteeDetailsCreate, MenteeDetailsUpdate, MenteeDetailsResponse,
    MentorSuggestionRequest, MentorSuggestionResponse, MentorshipInterestResponse,
    UserResponse, SuccessResponse
)
from app.services.user.services import mentee_service, mentorship_interest_service, user_service, mentor_service
from app.services.mentorship.mentor_suggestion_service import mentor_suggestion_service
from app.services.storage.file_upload_service import file_upload_service

router = APIRouter(prefix="/mentee", tags=["mentee"])


def convert_to_inr(amount: float, currency: str) -> float:
    """Convert a given amount from currency to INR using simple env-configurable rates.

    Environment overrides (optional): FX_USD_INR, FX_EUR_INR, FX_GBP_INR
    Defaults are sensible fallbacks if env vars are not set.
    """
    try:
        if amount is None:
            return amount
        code = (currency or "INR").upper()
        rates = {
            "INR": 1.0,
            "USD": float(os.getenv("FX_USD_INR", "83.0")),
            "EUR": float(os.getenv("FX_EUR_INR", "90.0")),
            "GBP": float(os.getenv("FX_GBP_INR", "105.0")),
        }
        rate = rates.get(code)
        if rate is None:
            # Unknown currency: assume already INR
            return amount
        return amount * rate
    except Exception:
        # Fail safe: return original amount if conversion fails
        return amount

@router.post("/details", response_model=MenteeDetailsResponse)
async def create_mentee_details(
    mentee_data: MenteeDetailsCreate,
    current_user = Depends(get_current_mentee_user)
):
    """Create mentee details"""
    try:
        # Ensure the user_id matches the authenticated user
        if mentee_data.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create details for another user"
            )
        
        mentee_details = await mentee_service.create_mentee_details(mentee_data)
        return mentee_details
        
    except HTTPException:
        raise
    except Exception as e:
        if "already exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mentee details already exist for this user"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create mentee details"
        )

@router.get("/details", response_model=MenteeDetailsResponse)
async def get_mentee_details(current_user = Depends(get_current_mentee_user)):
    """Get mentee details for current user"""
    try:
        mentee_details = await mentee_service.get_mentee_details_by_user_id(current_user.user_id)
        if not mentee_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentee details not found"
            )
        return mentee_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mentee details"
        )

@router.put("/details", response_model=MenteeDetailsResponse)
async def update_mentee_details(
    update_data: MenteeDetailsUpdate,
    current_user = Depends(get_current_mentee_user)
):
    """Update mentee details"""
    try:
        mentee_details = await mentee_service.update_mentee_details(current_user.user_id, update_data)
        if not mentee_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentee details not found"
            )
        return mentee_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update mentee details"
        )

@router.post("/suggest-mentors", response_model=List[MentorSuggestionResponse])
async def suggest_mentors(
    request: MentorSuggestionRequest,
    current_user = Depends(get_current_mentee_user)
):
    """Get mentor suggestions based on mentee profile"""
    try:
        suggestions = await mentor_suggestion_service.suggest_mentors(
            mentee_user_id=current_user.user_id,
            limit=request.limit,
            min_match_score=request.min_match_score
        )
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor suggestions: {str(e)}"
        )

@router.get("/accepted-mentorships")
async def get_accepted_mentorships(current_user = Depends(get_current_user)):
    """Get all accepted mentorship interests for the current mentee with mentor details"""
    try:
        # Allow mentee and parent; block others
        if current_user.role not in ["mentee", "parent"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Mentee or parent role required."
            )
        accepted_mentorships = await mentorship_interest_service.get_interests_by_mentee_and_status(
            mentee_id=current_user.user_id,
            status="accepted"
        )
        
        # Enhance each mentorship with full mentor details
        enhanced_mentorships = []
        for mentorship in accepted_mentorships:
            # Get full mentor details
            mentor_user = await user_service.get_user_by_id(mentorship.mentor_id)
            mentor_details = None
            
            if mentor_user:
                try:
                    mentor_details = await mentor_service.get_mentor_details_by_user_id(mentorship.mentor_id)
                except:
                    # If mentor details don't exist, we'll just use user info
                    pass
            
            mentor_details_dict = mentor_details.dict() if mentor_details else None

            # If mentorship fee exists, compute INR equivalent and attach as mentorship_fee_inr
            if mentor_details_dict and mentor_details_dict.get("mentorship_fee") is not None:
                original_fee = mentor_details_dict.get("mentorship_fee")
                currency = mentor_details_dict.get("currency", "INR")
                inr_fee = convert_to_inr(original_fee, currency)
                # Round to 2 decimals for currency display
                mentor_details_dict["mentorship_fee_inr"] = round(inr_fee, 2)

            enhanced_mentorship = {
                "id": mentorship.id,
                "mentee_id": mentorship.mentee_id,
                "mentor_id": mentorship.mentor_id,
                "status": mentorship.status,
                "message": mentorship.message,
                "mentee_notes": mentorship.mentee_notes,
                "mentor_response": mentorship.mentor_response,
                "created_at": mentorship.created_at,
                "updated_at": mentorship.updated_at,
                "mentor": {
                    "user_info": mentor_user.dict() if mentor_user else None,
                    "mentor_details": mentor_details_dict
                }
            }
            enhanced_mentorships.append(enhanced_mentorship)
        
        return enhanced_mentorships
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get accepted mentorships: {str(e)}"
        )


# Profile Picture Upload
@router.post("/profile-picture/upload", response_model=SuccessResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload a profile picture. If the user is a mentee, persist the URL to mentee details.
    For other roles, return the uploaded URL without persisting (until role-specific storage exists)."""
    try:
        # Upload new profile picture
        profile_pic_url = await file_upload_service.upload_profile_picture(
            file, current_user.user_id
        )

        # If mentee, persist in mentee details and clean up old file
        if current_user.role == "mentee":
            # Get current mentee details to check for existing profile picture
            current_details = await mentee_service.get_mentee_details_by_user_id(current_user.user_id)

            # Update mentee details with new profile picture URL
            await mentee_service.update_mentee_details(
                current_user.user_id,
                MenteeDetailsUpdate(profile_pic_url=profile_pic_url)
            )

            # Delete old profile picture if it exists
            if current_details and current_details.profile_pic_url:
                await file_upload_service.delete_profile_picture(current_details.profile_pic_url)

        # For other roles, we only return the URL for now
        return SuccessResponse(
            message="Profile picture uploaded successfully",
            data={"profile_pic_url": profile_pic_url}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload profile picture: {str(e)}"
        )


# Profile Picture URL Update (for manual URL updates)
class ProfilePicUpdateRequest(BaseModel):
    profile_pic_url: str


@router.put("/profile-picture", response_model=SuccessResponse)
async def update_profile_picture_url(
    request: ProfilePicUpdateRequest,
    current_user = Depends(get_current_mentee_user)
):
    """Update mentee profile picture URL manually"""
    try:
        # Get current mentee details to check for existing profile picture
        current_details = await mentee_service.get_mentee_details_by_user_id(current_user.user_id)
        
        # Update the profile picture URL in mentee details
        updated_details = await mentee_service.update_mentee_details(
            current_user.user_id,
            MenteeDetailsUpdate(profile_pic_url=request.profile_pic_url)
        )
        
        # Delete old profile picture if it exists and is different
        if (current_details and 
            current_details.profile_pic_url and 
            current_details.profile_pic_url != request.profile_pic_url):
            await file_upload_service.delete_profile_picture(current_details.profile_pic_url)
        
        return SuccessResponse(
            message="Profile picture URL updated successfully",
            data={"profile_pic_url": request.profile_pic_url}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile picture URL: {str(e)}"
        )


@router.delete("/profile-picture", response_model=SuccessResponse)
async def delete_profile_picture(
    current_user = Depends(get_current_mentee_user)
):
    """Delete mentee profile picture"""
    try:
        # Get current mentee details
        current_details = await mentee_service.get_mentee_details_by_user_id(current_user.user_id)
        
        if not current_details or not current_details.profile_pic_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No profile picture found"
            )
        
        # Delete from storage
        await file_upload_service.delete_profile_picture(current_details.profile_pic_url)
        
        # Update mentee details to remove profile picture URL
        await mentee_service.update_mentee_details(
            current_user.user_id,
            MenteeDetailsUpdate(profile_pic_url=None)
        )
        
        return SuccessResponse(
            message="Profile picture deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile picture: {str(e)}"
        )
