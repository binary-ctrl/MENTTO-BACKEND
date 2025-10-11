"""
Review API routes for mentor reviews
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query

from app.core.security.auth_dependencies import get_current_mentee_user, get_current_user
from app.models.models import (
    MentorReviewCreate, MentorReviewUpdate, MentorReviewResponse, 
    MentorReviewSummary, UserResponse
)
from app.services.review.review_service import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("/mentor", response_model=MentorReviewResponse)
async def create_mentor_review(
    review_data: MentorReviewCreate,
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Leave a review for a mentor"""
    try:
        review = await review_service.create_review(current_user.user_id, review_data)
        
        if not review:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create review"
            )
        
        return review
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review: {str(e)}"
        )

@router.get("/mentor/{mentor_id}", response_model=List[MentorReviewResponse])
async def get_mentor_reviews(
    mentor_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of reviews to return"),
    offset: int = Query(0, ge=0, description="Number of reviews to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all reviews for a specific mentor"""
    try:
        reviews = await review_service.get_reviews_by_mentor(mentor_id, limit, offset)
        return reviews
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor reviews: {str(e)}"
        )

@router.get("/mentor/{mentor_id}/summary", response_model=MentorReviewSummary)
async def get_mentor_review_summary(
    mentor_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get comprehensive review summary for a mentor"""
    try:
        summary = await review_service.get_mentor_review_summary(mentor_id)
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No reviews found for this mentor"
            )
        
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor review summary: {str(e)}"
        )

@router.get("/my-reviews", response_model=List[MentorReviewResponse])
async def get_my_reviews(
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Get all reviews written by the current mentee"""
    try:
        reviews = await review_service.get_reviews_by_mentee(current_user.user_id)
        return reviews
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get your reviews: {str(e)}"
        )

@router.get("/mentor/{mentor_id}/my-review", response_model=Optional[MentorReviewResponse])
async def get_my_review_for_mentor(
    mentor_id: str,
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Get the current mentee's review for a specific mentor (if exists)"""
    try:
        review = await review_service.get_review_by_mentee_and_mentor(current_user.user_id, mentor_id)
        return review
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get your review for this mentor: {str(e)}"
        )

@router.put("/{review_id}", response_model=MentorReviewResponse)
async def update_review(
    review_id: str,
    update_data: MentorReviewUpdate,
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Update an existing review"""
    try:
        review = await review_service.update_review(review_id, current_user.user_id, update_data)
        
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or you don't have permission to update it"
            )
        
        return review
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update review: {str(e)}"
        )

@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Delete a review"""
    try:
        success = await review_service.delete_review(review_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or you don't have permission to delete it"
            )
        
        return {"success": True, "message": "Review deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete review: {str(e)}"
        )
