"""
Mentorship API routes for managing mentorship interests
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status

from app.core.security.auth_dependencies import get_current_user, get_current_mentee_user, get_current_mentor_user
from app.models.models import (
    MentorshipInterestCreate, MentorshipInterestUpdate, MentorshipInterestResponse
)
from app.services.user.services import mentorship_interest_service

router = APIRouter(prefix="/mentorship", tags=["mentorship"])

@router.post("/interest", response_model=MentorshipInterestResponse)
async def create_mentorship_interest(
    interest_data: MentorshipInterestCreate,
    current_user = Depends(get_current_user)
):
    """Create a new mentorship interest (mentee to mentor)"""
    try:
        # Allow mentee and parent to create interests
        if current_user.role not in ["mentee", "parent"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Mentee or parent role required."
            )
        # Create the mentorship interest
        mentorship_interest = await mentorship_interest_service.create_interest(
            interest_data=interest_data,
            mentee_id=current_user.user_id
        )
        return mentorship_interest
        
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mentorship interest already exists for this mentor"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mentorship interest: {str(e)}"
        )

@router.get("/interest", response_model=List[MentorshipInterestResponse])
async def get_mentorship_interests(current_user = Depends(get_current_user)):
    """Get all mentorship interests for the current mentee"""
    try:
        # Allow mentee and parent to view their interests
        if current_user.role not in ["mentee", "parent"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Mentee or parent role required."
            )
        interests = await mentorship_interest_service.get_interests_by_mentee(current_user.user_id)
        return interests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentorship interests: {str(e)}"
        )

@router.get("/interest/mentor", response_model=List[MentorshipInterestResponse])
async def get_mentorship_interests_for_mentor(current_user = Depends(get_current_mentor_user)):
    """Get all mentorship interests received by the current mentor"""
    try:
        interests = await mentorship_interest_service.get_interests_by_mentor(current_user.user_id)
        return interests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentorship interests: {str(e)}"
        )

@router.get("/interest/pending", response_model=List[MentorshipInterestResponse])
async def get_pending_mentorship_interests(current_user = Depends(get_current_mentor_user)):
    """Get all pending mentorship interest requests for the current mentor"""
    try:
        pending_interests = await mentorship_interest_service.get_interests_by_mentor_and_status(
            mentor_id=current_user.user_id,
            status="pending"
        )
        return pending_interests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending mentorship interests: {str(e)}"
        )

@router.put("/interest/{interest_id}", response_model=MentorshipInterestResponse)
async def update_mentorship_interest(
    interest_id: str,
    update_data: MentorshipInterestUpdate,
    current_user = Depends(get_current_mentor_user)
):
    """Update a mentorship interest (mentor can accept/reject)"""
    try:
        updated_interest = await mentorship_interest_service.update_interest_status(
            interest_id=interest_id,
            update_data=update_data,
            mentor_id=current_user.user_id
        )
        return updated_interest
    except Exception as e:
        if "not found" in str(e).lower() or "not authorized" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentorship interest not found or not authorized"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mentorship interest: {str(e)}"
        )
