"""
User API routes
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

from app.core.security.auth_dependencies import get_current_user
from app.models.models import UserResponse, MenteeDetailsResponse, MentorDetailsResponse
from app.services.user.services import user_service, mentee_service, mentor_service
from app.services.questionnaire.questionnaire_service import questionnaire_service
from app.api.user.time_slots_routes import router as time_slots_router

router = APIRouter(prefix="/users", tags=["users"])

# Include time slots routes
router.include_router(time_slots_router)

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user = await user_service.get_user_by_id(current_user.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

@router.get("/me/details")
async def get_current_user_details(current_user = Depends(get_current_user)):
    """Get current user's detailed profile based on their role (mentee, mentor, or parent)"""
    try:
        user_role = current_user.role
        
        if user_role == "mentee":
            # Fetch mentee details
            mentee_details = await mentee_service.get_mentee_details_by_user_id(current_user.user_id)
            return {
                "user_type": "mentee",
                "details": mentee_details,
                "has_details": mentee_details is not None,
                "message": "Mentee details not set up yet" if mentee_details is None else None
            }
            
        elif user_role == "mentor":
            # Fetch mentor details
            mentor_details = await mentor_service.get_mentor_details_by_user_id(current_user.user_id)
            return {
                "user_type": "mentor",
                "details": mentor_details,
                "has_details": mentor_details is not None,
                "message": "Mentor details not set up yet" if mentor_details is None else None
            }
        elif user_role == "parent":
            # Fetch parent details from questionnaire responses
            questionnaire_details = await questionnaire_service.get_questionnaire_response_by_user_id(current_user.user_id)
            return {
                "user_type": "parent",
                "details": questionnaire_details,
                "has_details": questionnaire_details is not None,
                "message": "Questionnaire not submitted yet" if questionnaire_details is None else None
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role. Must be 'mentee', 'mentor' or 'parent'"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user details: {str(e)}"
        )
