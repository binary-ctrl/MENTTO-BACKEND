"""
Admin API routes for managing mentors and users
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse

from app.core.database import get_supabase
from app.core.security.auth_dependencies import get_current_user
from app.models.models import MentorDetailsResponse, UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])

def check_admin_access(current_user):
    """Check if user has admin access (mentor, admin, mentee, or parent)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    print(f"Current user role: {current_user.role}")
    
    # Allow mentors, admins, mentees, and parents to access admin endpoints for now
    # You can modify this logic based on your requirements
    if current_user.role not in ["mentor", "admin", "mentee", "parent"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin, mentor, mentee, or parent access required."
        )

class PaginatedResponse:
    def __init__(self, items: List, total: int, page: int, size: int):
        self.items = items
        self.total = total
        self.page = page
        self.size = size
        self.total_pages = (total + size - 1) // size
        self.has_next = page < self.total_pages
        self.has_prev = page > 1

    def dict(self):
        return {
            "items": self.items,
            "pagination": {
                "total": self.total,
                "page": self.page,
                "size": self.size,
                "total_pages": self.total_pages,
                "has_next": self.has_next,
                "has_prev": self.has_prev
            }
        }

@router.get("/mentors")
async def get_all_mentors(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)"),
    search: Optional[str] = Query(None, description="Search by name, email, or university"),
    country: Optional[str] = Query(None, description="Filter by study country"),
    university: Optional[str] = Query(None, description="Filter by university"),
    current_user = Depends(get_current_user)
):
    """
    Get all mentors with pagination and optional filtering
    """
    try:
        # Check admin access
        check_admin_access(current_user)
        
        # Get Supabase client
        supabase = get_supabase()
        
        # First, get all users with mentor role
        print("Fetching mentor users...")
        users_result = supabase.table("users").select("user_id, full_name, email, role, created_at, updated_at").eq("role", "mentor").execute()
        print(f"Users result: {users_result}")
        
        if not users_result.data:
            print("No mentor users found")
            return {
                "items": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "size": size,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }
        
        mentor_user_ids = [user["user_id"] for user in users_result.data]
        print(f"Found {len(mentor_user_ids)} mentor users")
        
        if not mentor_user_ids:
            return {
                "items": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "size": size,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }
        
        # Get mentor details for these users (if they exist)
        print("Fetching mentor details...")
        mentor_details_result = supabase.table("mentor_details").select("*").in_("user_id", mentor_user_ids).execute()
        print(f"Mentor details result: {mentor_details_result}")
        mentor_details_data = mentor_details_result.data or []
        
        # Create a lookup for mentor details
        mentor_details_lookup = {detail["user_id"]: detail for detail in mentor_details_data}
        
        # Get current user's mentorship interests to filter out connected mentors
        current_user_id = current_user.user_id
        print(f"Filtering out mentors already connected to user: {current_user_id}")
        
        # Get mentorship interests where current user is mentee
        mentorship_interests_result = supabase.table("mentorship_interest").select("mentor_id").eq("mentee_id", current_user_id).execute()
        connected_mentor_ids = set()
        if mentorship_interests_result.data:
            connected_mentor_ids = {interest["mentor_id"] for interest in mentorship_interests_result.data}
        
        print(f"Found {len(connected_mentor_ids)} connected mentors to filter out")
        
        # Combine user data with mentor details (if available) and filter out connected mentors
        all_mentors = []
        for user in users_result.data:
            # Skip if this mentor is already connected to the current user
            if user["user_id"] in connected_mentor_ids:
                print(f"Filtering out connected mentor: {user['user_id']}")
                continue
                
            mentor_detail = mentor_details_lookup.get(user["user_id"])
            combined_data = {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"],
                "created_at": user["created_at"],
                "updated_at": user["updated_at"],
                "mentor_details": mentor_detail  # Will be None if no details exist
            }
            all_mentors.append(combined_data)
        
        # Apply filters
        if country:
            all_mentors = [
                mentor for mentor in all_mentors
                if mentor.get("mentor_details") and mentor["mentor_details"].get("study_country") == country
            ]
            
        if university:
            all_mentors = [
                mentor for mentor in all_mentors
                if mentor.get("mentor_details") and university.lower() in mentor["mentor_details"].get("university_associated", "").lower()
            ]
        
        # Apply search filter in Python
        if search:
            search_lower = search.lower()
            all_mentors = [
                mentor for mentor in all_mentors
                if (search_lower in mentor.get("full_name", "").lower() or
                    search_lower in mentor.get("email", "").lower() or
                    (mentor.get("mentor_details") and (
                        search_lower in mentor["mentor_details"].get("first_name", "").lower() or
                        search_lower in mentor["mentor_details"].get("last_name", "").lower() or
                        search_lower in mentor["mentor_details"].get("university_associated", "").lower()
                    )))
            ]
        
        # Calculate pagination
        total = len(all_mentors)
        offset = (page - 1) * size
        mentors = all_mentors[offset:offset + size]
        
        # Transform the results
        mentor_list = []
        for mentor in mentors:
            mentor_details = mentor.get("mentor_details")
            
            # Build mentor details response: include ALL columns from mentor_details row if present
            mentor_details_response = mentor_details if mentor_details else None
            
            mentor_data = {
                "mentor_details": mentor_details_response,
                "user_details": {
                    "user_id": mentor.get("user_id"),
                    "full_name": mentor.get("full_name"),
                    "email": mentor.get("email"),
                    "role": mentor.get("role"),
                    "created_at": mentor.get("created_at"),
                    "updated_at": mentor.get("updated_at")
                }
            }
            mentor_list.append(mentor_data)
        
        # Create paginated response
        paginated_response = PaginatedResponse(
            items=mentor_list,
            total=total,
            page=page,
            size=size
        )
        
        return paginated_response.dict()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_all_mentors: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch mentors: {str(e)}"
        )

@router.get("/mentors/{mentor_id}")
async def get_mentor_by_id(mentor_id: str, current_user = Depends(get_current_user)):
    """
    Get a specific mentor by user_id
    """
    try:
        # Check admin access
        check_admin_access(current_user)
        
        # Get Supabase client
        supabase = get_supabase()
        
        # First check if user is a mentor
        user_result = supabase.table("users").select("*").eq("user_id", mentor_id).eq("role", "mentor").execute()
        
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor not found"
            )
        
        # Get mentor details
        mentor_result = supabase.table("mentor_details").select("*").eq("user_id", mentor_id).execute()
        
        if not mentor_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor details not found"
            )
        
        mentor = mentor_result.data[0]
        user_data = user_result.data[0]
        
        mentor_data = {
            "mentor_details": {
                "user_id": mentor.get("user_id"),
                "first_name": mentor.get("first_name"),
                "last_name": mentor.get("last_name"),
                "phone_number": mentor.get("phone_number"),
                "email": mentor.get("email"),
                "study_country": mentor.get("study_country"),
                "university_associated": mentor.get("university_associated"),
                "graduation_date": mentor.get("graduation_date"),
                "university_relationship": mentor.get("university_relationship"),
                "course_enrolled": mentor.get("course_enrolled"),
                "education_level": mentor.get("education_level"),
                "industries_worked": mentor.get("industries_worked"),
                "current_occupation": mentor.get("current_occupation"),
                "work_experience_years": mentor.get("work_experience_years"),
                "mentorship_fee": mentor.get("mentorship_fee"),
                "previous_mentoring_experience": mentor.get("previous_mentoring_experience"),
                "mentorship_hours_per_week": mentor.get("mentorship_hours_per_week"),
                "created_at": mentor.get("created_at"),
                "updated_at": mentor.get("updated_at")
            },
            "user_details": {
                "user_id": user_data.get("user_id"),
                "full_name": user_data.get("full_name"),
                "email": user_data.get("email"),
                "role": user_data.get("role"),
                "created_at": user_data.get("created_at"),
                "updated_at": user_data.get("updated_at")
            }
        }
        
        return mentor_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch mentor: {str(e)}"
        )

@router.get("/mentors/stats")
async def get_mentor_stats(current_user = Depends(get_current_user)):
    """
    Get mentor statistics
    """
    try:
        # Check admin access
        check_admin_access(current_user)
        
        # Get Supabase client
        supabase = get_supabase()
        
        # Total mentors count
        total_result = supabase.table("users").select("user_id").eq("role", "mentor").execute()
        total_mentors = len(total_result.data)
        
        # Get all mentor details for statistics
        mentors_result = supabase.table("mentor_details").select(
            "study_country, university_associated"
        ).execute()
        
        mentors = mentors_result.data
        
        # Calculate statistics
        country_stats = {}
        university_stats = {}
        
        for mentor in mentors:
            country = mentor.get("study_country")
            university = mentor.get("university_associated")
            
            if country:
                country_stats[country] = country_stats.get(country, 0) + 1
            
            if university:
                university_stats[university] = university_stats.get(university, 0) + 1
        
        # Sort and format results
        by_country = [
            {"study_country": country, "count": count}
            for country, count in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)
        ]
        
        top_universities = [
            {"university_associated": university, "count": count}
            for university, count in sorted(university_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return {
            "total_mentors": total_mentors,
            "by_country": by_country,
            "top_universities": top_universities
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch mentor stats: {str(e)}"
        )
