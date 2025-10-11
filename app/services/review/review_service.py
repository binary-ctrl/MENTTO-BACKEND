"""
Review Service for managing mentor reviews
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import get_supabase
from app.models.models import (
    MentorReviewCreate, MentorReviewUpdate, MentorReviewResponse, 
    MentorReviewSummary, SessionQuality
)

logger = logging.getLogger(__name__)

class ReviewService:
    def __init__(self):
        self.supabase = get_supabase()

    async def create_review(self, mentee_id: str, review_data: MentorReviewCreate) -> Optional[MentorReviewResponse]:
        """Create a new mentor review"""
        try:
            # Check if review already exists for this mentee-mentor pair
            existing_review = await self.get_review_by_mentee_and_mentor(mentee_id, review_data.mentor_id)
            if existing_review:
                raise ValueError("Review already exists for this mentor. You can only leave one review per mentor.")
            
            # Verify mentorship relationship exists
            if review_data.mentorship_interest_id:
                mentorship_check = self.supabase.table("mentorship_interest").select("id, status").eq("id", review_data.mentorship_interest_id).eq("mentee_id", mentee_id).eq("mentor_id", review_data.mentor_id).execute()
                if not mentorship_check.data:
                    raise ValueError("Invalid mentorship interest ID or no relationship found")
            
            # Prepare review data for database
            review_dict = {
                "mentee_id": mentee_id,
                "mentor_id": review_data.mentor_id,
                "mentorship_interest_id": review_data.mentorship_interest_id,
                "overall_rating": review_data.overall_rating,
                "session_qualities": [quality.value for quality in review_data.session_qualities],
                "review_text": review_data.review_text
            }
            
            # Insert review
            result = self.supabase.table("mentor_reviews").insert(review_dict).execute()
            
            if result.data:
                review_id = result.data[0]["id"]
                return await self.get_review_by_id(review_id)
            else:
                logger.error(f"Failed to create review for mentee {mentee_id} and mentor {review_data.mentor_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating review: {e}")
            raise

    async def get_review_by_id(self, review_id: str) -> Optional[MentorReviewResponse]:
        """Get a review by ID with mentee details"""
        try:
            result = self.supabase.table("mentor_reviews").select(
                "*, users!mentor_reviews_mentee_id_fkey(full_name, email)"
            ).eq("id", review_id).execute()
            
            if result.data:
                review_data = result.data[0]
                return self._convert_to_review_response(review_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting review by ID {review_id}: {e}")
            return None

    async def get_review_by_mentee_and_mentor(self, mentee_id: str, mentor_id: str) -> Optional[MentorReviewResponse]:
        """Get review by mentee and mentor IDs"""
        try:
            result = self.supabase.table("mentor_reviews").select(
                "*, users!mentor_reviews_mentee_id_fkey(full_name, email)"
            ).eq("mentee_id", mentee_id).eq("mentor_id", mentor_id).execute()
            
            if result.data:
                review_data = result.data[0]
                return self._convert_to_review_response(review_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting review by mentee {mentee_id} and mentor {mentor_id}: {e}")
            return None

    async def get_reviews_by_mentor(self, mentor_id: str, limit: int = 10, offset: int = 0) -> List[MentorReviewResponse]:
        """Get all reviews for a specific mentor"""
        try:
            result = self.supabase.table("mentor_reviews").select(
                "*, users!mentor_reviews_mentee_id_fkey(full_name, email)"
            ).eq("mentor_id", mentor_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            reviews = []
            for review_data in result.data:
                review = self._convert_to_review_response(review_data)
                if review:
                    reviews.append(review)
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting reviews for mentor {mentor_id}: {e}")
            return []

    async def get_reviews_by_mentee(self, mentee_id: str) -> List[MentorReviewResponse]:
        """Get all reviews written by a specific mentee"""
        try:
            result = self.supabase.table("mentor_reviews").select(
                "*, users!mentor_reviews_mentee_id_fkey(full_name, email)"
            ).eq("mentee_id", mentee_id).order("created_at", desc=True).execute()
            
            reviews = []
            for review_data in result.data:
                review = self._convert_to_review_response(review_data)
                if review:
                    reviews.append(review)
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting reviews by mentee {mentee_id}: {e}")
            return []

    async def update_review(self, review_id: str, mentee_id: str, update_data: MentorReviewUpdate) -> Optional[MentorReviewResponse]:
        """Update an existing review"""
        try:
            # Verify the review belongs to the mentee
            existing_review = await self.get_review_by_id(review_id)
            if not existing_review or existing_review.mentee_id != mentee_id:
                raise ValueError("Review not found or you don't have permission to update it")
            
            # Prepare update data
            update_dict = {}
            if update_data.overall_rating is not None:
                update_dict["overall_rating"] = update_data.overall_rating
            if update_data.session_qualities is not None:
                update_dict["session_qualities"] = [quality.value for quality in update_data.session_qualities]
            if update_data.review_text is not None:
                update_dict["review_text"] = update_data.review_text
            
            if not update_dict:
                return existing_review
            
            # Update review
            result = self.supabase.table("mentor_reviews").update(update_dict).eq("id", review_id).execute()
            
            if result.data:
                return await self.get_review_by_id(review_id)
            return None
            
        except Exception as e:
            logger.error(f"Error updating review {review_id}: {e}")
            raise

    async def delete_review(self, review_id: str, mentee_id: str) -> bool:
        """Delete a review"""
        try:
            # Verify the review belongs to the mentee
            existing_review = await self.get_review_by_id(review_id)
            if not existing_review or existing_review.mentee_id != mentee_id:
                raise ValueError("Review not found or you don't have permission to delete it")
            
            result = self.supabase.table("mentor_reviews").delete().eq("id", review_id).execute()
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error deleting review {review_id}: {e}")
            raise

    async def get_mentor_review_summary(self, mentor_id: str) -> Optional[MentorReviewSummary]:
        """Get comprehensive review summary for a mentor"""
        try:
            # Get all reviews for the mentor
            reviews_result = self.supabase.table("mentor_reviews").select("*").eq("mentor_id", mentor_id).execute()
            
            if not reviews_result.data:
                return MentorReviewSummary(
                    mentor_id=mentor_id,
                    total_reviews=0,
                    average_rating=0.0,
                    rating_distribution={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                    quality_counts={},
                    recent_reviews=[]
                )
            
            reviews = reviews_result.data
            
            # Calculate statistics
            total_reviews = len(reviews)
            total_rating = sum(review["overall_rating"] for review in reviews)
            average_rating = round(total_rating / total_reviews, 2) if total_reviews > 0 else 0.0
            
            # Rating distribution
            rating_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
            for review in reviews:
                rating = str(review["overall_rating"])
                rating_distribution[rating] += 1
            
            # Quality counts
            quality_counts = {}
            for review in reviews:
                for quality in review.get("session_qualities", []):
                    quality_counts[quality] = quality_counts.get(quality, 0) + 1
            
            # Get recent reviews (last 5)
            recent_reviews = await self.get_reviews_by_mentor(mentor_id, limit=5)
            
            return MentorReviewSummary(
                mentor_id=mentor_id,
                total_reviews=total_reviews,
                average_rating=average_rating,
                rating_distribution=rating_distribution,
                quality_counts=quality_counts,
                recent_reviews=recent_reviews
            )
            
        except Exception as e:
            logger.error(f"Error getting mentor review summary for {mentor_id}: {e}")
            return None

    def _convert_to_review_response(self, review_data: Dict[str, Any]) -> Optional[MentorReviewResponse]:
        """Convert database record to MentorReviewResponse"""
        try:
            # Extract mentee details from joined user data
            mentee_name = None
            mentee_email = None
            if review_data.get("users"):
                mentee_name = review_data["users"].get("full_name")
                mentee_email = review_data["users"].get("email")
            
            return MentorReviewResponse(
                id=review_data["id"],
                mentee_id=review_data["mentee_id"],
                mentor_id=review_data["mentor_id"],
                mentorship_interest_id=review_data.get("mentorship_interest_id"),
                overall_rating=review_data["overall_rating"],
                session_qualities=review_data.get("session_qualities", []),
                review_text=review_data.get("review_text"),
                created_at=datetime.fromisoformat(review_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(review_data["updated_at"].replace('Z', '+00:00')),
                mentee_name=mentee_name,
                mentee_email=mentee_email
            )
        except Exception as e:
            logger.error(f"Error converting review data to response: {e}")
            return None

# Service instance
review_service = ReviewService()
