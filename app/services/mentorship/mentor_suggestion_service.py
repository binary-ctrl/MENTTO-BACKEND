"""
Mentor Suggestion Service for matching mentees with compatible mentors
"""

import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
from app.core.database import get_supabase
from app.models.models import (
    MenteeDetailsResponse, 
    MentorDetailsResponse, 
    MentorSuggestionResponse,
    UserResponse
)

logger = logging.getLogger(__name__)

class MentorSuggestionService:
    def __init__(self):
        self.supabase = get_supabase()
    
    async def suggest_mentors(
        self, 
        mentee_user_id: str, 
        limit: int = 10, 
        min_match_score: float = 0.3
    ) -> List[MentorSuggestionResponse]:
        """Suggest mentors based on mentee profile compatibility"""
        try:
            # Get mentee details
            mentee_details = await self._get_mentee_details(mentee_user_id)
            logger.info(f"DEBUG: Mentee details for {mentee_user_id}: {mentee_details}")
            if not mentee_details:
                logger.warning(f"No mentee details found for user {mentee_user_id}")
                return []
            
            # Get all mentors with their details
            mentors = await self._get_all_mentors()
            logger.info(f"DEBUG: Found {len(mentors)} mentors in database")
            if not mentors:
                logger.warning("No mentors found in database")
                return []
            
            # Calculate match scores and reasons
            suggestions = []
            for mentor in mentors:
                match_score, match_reasons = self._calculate_match_score(mentee_details, mentor)
                logger.info(f"DEBUG: Mentor {mentor.get('user_id', 'unknown')} match score: {match_score}")
                
                if match_score >= min_match_score:
                    suggestion = MentorSuggestionResponse(
                        mentor_id=mentor['user_id'],
                        mentor_name=f"{mentor['first_name']} {mentor['last_name']}",
                        mentor_email=mentor['email'],
                        match_score=match_score,
                        match_reasons=match_reasons,
                        mentor_details=MentorDetailsResponse(**mentor),
                        user_details=UserResponse(**mentor['user_details'])
                    )
                    suggestions.append(suggestion)
            
            # Sort by match score (highest first) and limit results
            suggestions.sort(key=lambda x: x.match_score, reverse=True)
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Error suggesting mentors: {e}")
            raise
    
    async def _get_mentee_details(self, user_id: str) -> Dict[str, Any]:
        """Get mentee details from database"""
        try:
            result = self.supabase.table("mentee_details").select("*").eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting mentee details: {e}")
            return None
    
    async def _get_all_mentors(self) -> List[Dict[str, Any]]:
        """Get all mentors with their user details"""
        try:
            # Get mentors with their user details
            result = self.supabase.table("mentor_details").select(
                "*, users!inner(*)"
            ).execute()
            
            mentors = []
            for mentor in result.data:
                mentor['user_details'] = mentor['users']
                mentors.append(mentor)
            
            return mentors
        except Exception as e:
            logger.error(f"Error getting mentors: {e}")
            return []
    
    def _calculate_match_score(
        self, 
        mentee: Dict[str, Any], 
        mentor: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """Calculate compatibility score between mentee and mentor"""
        match_reasons = []
        total_score = 0.0
        max_score = 0.0
        
        # 1. Country/Study Location Match (30% weight)
        mentee_countries = mentee.get('countries_considering', [])
        mentor_country = mentor.get('study_country', '')
        
        if mentor_country and mentor_country in mentee_countries:
            total_score += 30
            match_reasons.append(f"Studying in {mentor_country} (your target country)")
        max_score += 30
        
        # 2. Course/Field Match (25% weight)
        mentee_courses = mentee.get('courses_exploring', [])
        mentor_course = mentor.get('course_enrolled', '')
        
        if mentor_course and any(course.lower() in mentor_course.lower() or 
                               mentor_course.lower() in course.lower() 
                               for course in mentee_courses):
            total_score += 25
            match_reasons.append(f"Similar course: {mentor_course}")
        max_score += 25
        
        # 3. University Match (20% weight)
        mentee_universities = mentee.get('universities_exploring', [])
        mentor_university = mentor.get('university_associated', '')
        
        if mentor_university and any(uni.lower() in mentor_university.lower() or 
                                   mentor_university.lower() in uni.lower() 
                                   for uni in mentee_universities):
            total_score += 20
            match_reasons.append(f"From {mentor_university} (your target university)")
        max_score += 20
        
        # 4. Industry/Work Experience Match (15% weight)
        mentee_industries = mentee.get('target_industry', [])
        mentor_industries = mentor.get('industries_worked', [])
        
        if mentee_industries and mentor_industries:
            common_industries = set(mentee_industries) & set(mentor_industries)
            if common_industries:
                industry_score = (len(common_industries) / len(mentee_industries)) * 15
                total_score += industry_score
                match_reasons.append(f"Work experience in: {', '.join(common_industries)}")
        max_score += 15
        
        # 5. Education Level Match (10% weight)
        mentee_education = mentee.get('education_level', '')
        mentor_education = mentor.get('education_level', '')
        
        if mentee_education and mentor_education and mentee_education == mentor_education:
            total_score += 10
            match_reasons.append(f"Same education level: {mentor_education}")
        max_score += 10
        
        # Calculate final score as percentage
        final_score = (total_score / max_score) if max_score > 0 else 0.0
        
        # Add bonus points for specific matches
        if mentor.get('previous_mentoring_experience'):
            final_score += 0.05  # 5% bonus for experienced mentors
            match_reasons.append("Has previous mentoring experience")
        
        if mentor.get('mentorship_hours_per_week', 0) >= 5:
            final_score += 0.05  # 5% bonus for available mentors
            match_reasons.append("Highly available for mentorship")
        
        # Cap the score at 1.0
        final_score = min(final_score, 1.0)
        
        return final_score, match_reasons


# Service instance
mentor_suggestion_service = MentorSuggestionService()
