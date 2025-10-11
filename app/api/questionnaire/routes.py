"""
Questionnaire API routes
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional

from app.core.security.auth_dependencies import get_current_user
from app.models.models import (
    QuestionnaireDetailsCreate, 
    QuestionnaireDetailsUpdate, 
    QuestionnaireDetailsResponse,
    SuccessResponse
)
from app.services.questionnaire.questionnaire_service import questionnaire_service

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])


@router.post("/submit", response_model=QuestionnaireDetailsResponse)
async def submit_questionnaire(
    questionnaire_data: QuestionnaireDetailsCreate,
    current_user = Depends(get_current_user)
):
    """Submit a new questionnaire response"""
    try:
        # Set the user_id from the current authenticated user
        questionnaire_data.user_id = current_user.user_id
        
        response = await questionnaire_service.create_questionnaire_response(questionnaire_data)
        return response
        
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Questionnaire response already exists for this user"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit questionnaire: {str(e)}"
        )


@router.get("/my-response", response_model=QuestionnaireDetailsResponse)
async def get_my_questionnaire_response(current_user = Depends(get_current_user)):
    """Get current user's questionnaire response"""
    try:
        response = await questionnaire_service.get_questionnaire_response_by_user_id(current_user.user_id)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire response not found"
            )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire response: {str(e)}"
        )


@router.put("/update", response_model=QuestionnaireDetailsResponse)
async def update_questionnaire_response(
    update_data: QuestionnaireDetailsUpdate,
    current_user = Depends(get_current_user)
):
    """Update current user's questionnaire response"""
    try:
        response = await questionnaire_service.update_questionnaire_response(
            current_user.user_id, 
            update_data
        )
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire response not found"
            )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update questionnaire response: {str(e)}"
        )


@router.delete("/delete", response_model=SuccessResponse)
async def delete_questionnaire_response(current_user = Depends(get_current_user)):
    """Delete current user's questionnaire response"""
    try:
        success = await questionnaire_service.delete_questionnaire_response(current_user.user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire response not found"
            )
        return SuccessResponse(message="Questionnaire response deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete questionnaire response: {str(e)}"
        )


@router.get("/responses", response_model=List[QuestionnaireDetailsResponse])
async def get_all_questionnaire_responses(
    limit: int = Query(100, ge=1, le=1000, description="Number of responses to return"),
    offset: int = Query(0, ge=0, description="Number of responses to skip"),
    current_user = Depends(get_current_user)
):
    """Get all questionnaire responses (admin only)"""
    try:
        # Check if user is admin (you might want to implement proper admin role checking)
        if current_user.role != "admin":  # Assuming you have an admin role
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
            
        responses = await questionnaire_service.get_all_questionnaire_responses(limit, offset)
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire responses: {str(e)}"
        )


@router.get("/responses/by-country/{country}", response_model=List[QuestionnaireDetailsResponse])
async def get_questionnaire_responses_by_country(
    country: str,
    current_user = Depends(get_current_user)
):
    """Get questionnaire responses filtered by country (admin only)"""
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
            
        responses = await questionnaire_service.get_questionnaire_responses_by_country(country)
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire responses by country: {str(e)}"
        )


@router.get("/responses/by-education-level/{education_level}", response_model=List[QuestionnaireDetailsResponse])
async def get_questionnaire_responses_by_education_level(
    education_level: str,
    current_user = Depends(get_current_user)
):
    """Get questionnaire responses filtered by education level (admin only)"""
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
            
        responses = await questionnaire_service.get_questionnaire_responses_by_education_level(education_level)
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire responses by education level: {str(e)}"
        )


@router.get("/statistics")
async def get_questionnaire_statistics(current_user = Depends(get_current_user)):
    """Get questionnaire statistics (admin only)"""
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
            
        statistics = await questionnaire_service.get_questionnaire_statistics()
        return statistics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire statistics: {str(e)}"
        )


@router.get("/options")
async def get_questionnaire_options():
    """Get all available options for questionnaire fields (public endpoint)"""
    return {
        "why_study_abroad": [
            "A Higher Quality Education",
            "B Global Exposure", 
            "C Access to niche Programs",
            "D Personal Growth & Independence",
            "E Immigration and Settlement Opportunities",
            "F Networking Opportunities",
            "G Not Sure",
            "H Others"
        ],
        "year_planning_abroad": ["2026", "2027", "2028", "2029"],
        "finance_education": [
            "A Personal Savings",
            "B Scholarship or Grants",
            "C Education Loan",
            "D Family Support",
            "E Part-Time Work or Assistantships",
            "F Employer Sponsorship"
        ],
        "current_stage": [
            "A Just started researching",
            "B Shortlisting Courses",
            "C Shortlisting Universities",
            "D Shortlisting Countries",
            "E Preparing for GMAT/GRE/SAT",
            "F Preparing for IELTS/TOEFL/Duolingo",
            "G Application Process",
            "H Interview Stage",
            "I Deciding which university offer to accept",
            "J Already Graduated, looking for job advice and assistance",
            "K Looking for accommodation",
            "L Apply for my visa",
            "M Ready to go study abroad"
        ],
        "research_methods": [
            "A Online Resources",
            "B University brochures/seminars/websites",
            "C Connected with Alumni",
            "D Connect with Relatives and Friends",
            "E Career Consultants",
            "F Other"
        ],
        "countries_considering": [
            "A UK",
            "B Ireland", 
            "C Canada",
            "E Germany",
            "F Australia",
            "G France",
            "H Italy",
            "I Singapore",
            "J Hong Kong",
            "K Spain",
            "L Other"
        ],
        "planning_settle_abroad": ["Yes", "No", "Maybe"],
        "target_industry": [
            "A Technology/Software",
            "B Marketing/Advertising",
            "C Sales/Business Development",
            "D Education/EdTech",
            "E Finance/Banking",
            "F Healthcare",
            "G E-Commerce",
            "H Consulting",
            "I Customer Success/Support",
            "J Human Resources",
            "K Operations/Logistics",
            "L Fashion/Luxury",
            "M Agriculture",
            "N Other"
        ],
        "education_level": ["Undergraduate", "Masters", "PhD", "MPhil", "Other"],
        "concerns_worries": [
            "A Choosing the wrong stream or course",
            "B Coping with academic pressure",
            "C Uncertainty about future job opportunities",
            "E Financial affordability of future studies",
            "F Follow friends instead of their own interests",
            "G Your lack of understanding regarding the next steps",
            "H Settling and managing things abroad"
        ],
        "support_exploring_options": ["A", "B", "C", "D", "E"],
        "support_needed": [
            "A Career guidance and mentoring",
            "B Exposure to different fields and opportunities (e.g. workshops, internships, webinars)",
            "C Help with decision-making and planning",
            "D Motivation and encouragement to build confidence",
            "E Information about universities, courses, and exams"
        ],
        "how_mentto_help": [
            "A General guidance and advice",
            "B Navigating different countries, universities, and courses",
            "C Exploring study abroad experiences and cultures",
            "D Assistance with the application process",
            "E Application review",
            "F Making the right decision (course, university, or country)",
            "G Industry-specific insights and knowledge",
            "H Other"
        ],
        "how_found_mentto": ["LinkedIn", "Instagram", "Online Search", "Friends/Family", "Other"]
    }
