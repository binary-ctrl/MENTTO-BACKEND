"""
Admin API routes for managing mentors and users
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_supabase
from app.core.security.auth_dependencies import get_current_user
from app.core.security.admin_auth import get_current_admin
from app.models.models import MentorDetailsResponse, UserResponse, MentorVerificationUpdate, AdminAccountCreate, AdminAccountResponse
from app.services.admin.admin_service import admin_service
from app.services.user.services import mentor_service

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
    verification_status: Optional[str] = Query(None, description="Filter by verification status (verified, pending, rejected)"),
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
        
        # Check if current user is an admin
        current_user_id = current_user.user_id
        is_current_user_admin = await admin_service.is_admin_user(current_user_id)
        print(f"Current user {current_user_id} is admin: {is_current_user_admin}")
        
        # Get admin user IDs to filter out from mentor list (only if current user is not an admin)
        admin_user_ids = set()
        if not is_current_user_admin:
            print("Fetching admin user IDs to exclude...")
            admin_accounts_result = supabase.table("admin_accounts").select("user_id").eq("is_active", True).execute()
            if admin_accounts_result.data:
                admin_user_ids = {admin["user_id"] for admin in admin_accounts_result.data}
            print(f"Found {len(admin_user_ids)} admin users to filter out")
        
        # Get current user's mentorship interests to filter out connected mentors (only if current user is not an admin)
        connected_mentor_ids = set()
        if not is_current_user_admin:
            print(f"Filtering out mentors already connected to user: {current_user_id}")
            # Get mentorship interests where current user is mentee
            mentorship_interests_result = supabase.table("mentorship_interest").select("mentor_id").eq("mentee_id", current_user_id).execute()
            if mentorship_interests_result.data:
                connected_mentor_ids = {interest["mentor_id"] for interest in mentorship_interests_result.data}
            print(f"Found {len(connected_mentor_ids)} connected mentors to filter out")
        
        # Combine user data with mentor details (if available) and filter out connected mentors and admin users
        all_mentors = []
        for user in users_result.data:
            # Skip if this mentor is an admin user
            if user["user_id"] in admin_user_ids:
                print(f"Filtering out admin user: {user['user_id']}")
                continue
                
            # Skip if this mentor is already connected to the current user
            if user["user_id"] in connected_mentor_ids:
                print(f"Filtering out connected mentor: {user['user_id']}")
                continue
                
            mentor_detail = mentor_details_lookup.get(user["user_id"])
            
            # Skip if mentor doesn't have details
            if not mentor_detail:
                print(f"Filtering out mentor without details: {user['user_id']}")
                continue
                
            # Always exclude mentors with pending verification status
            if mentor_detail.get("verification_status") == "pending":
                print(f"Filtering out mentor with pending verification status: {user['user_id']}")
                continue
                
            # Apply verification status filter if specified (only for non-admin users)
            if not is_current_user_admin and verification_status and mentor_detail.get("verification_status") != verification_status:
                print(f"Filtering out mentor with different verification status: {user['user_id']} (status: {mentor_detail.get('verification_status', 'null')}, filter: {verification_status})")
                continue
            
            combined_data = {
                "user_id": user["user_id"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"],
                "created_at": user["created_at"],
                "updated_at": user["updated_at"],
                "mentor_details": mentor_detail
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

@router.get("/mentors/all", response_model=dict)
async def get_all_mentors_for_admin(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status (verified, pending, rejected)"),
    current_admin = Depends(get_current_admin)
):
    """
    Get ALL mentors for admin verification management (excludes admin users)
    """
    try:
        supabase = get_supabase()
        
        # Get admin user IDs to filter out from mentor list
        print("Fetching admin user IDs to exclude...")
        admin_accounts_result = supabase.table("admin_accounts").select("user_id").eq("is_active", True).execute()
        admin_user_ids = set()
        if admin_accounts_result.data:
            admin_user_ids = {admin["user_id"] for admin in admin_accounts_result.data}
        print(f"Found {len(admin_user_ids)} admin users to filter out")
        
        # Get all mentor details first (without pagination to filter admin users)
        query = supabase.table("mentor_details").select("*")
        
        # Apply verification status filter if specified
        if verification_status:
            query = query.eq("verification_status", verification_status)
        
        # Get all results first
        result = query.execute()
        all_mentor_details = result.data or []
        
        # Filter out admin users from mentor details
        filtered_mentor_details = []
        for mentor_detail in all_mentor_details:
            if mentor_detail["user_id"] not in admin_user_ids:
                filtered_mentor_details.append(mentor_detail)
        
        # Calculate total after filtering
        total = len(filtered_mentor_details)
        
        # Apply pagination to filtered results
        offset = (page - 1) * size
        paginated_mentor_details = filtered_mentor_details[offset:offset + size]
        
        # Get corresponding user details for paginated mentors
        user_ids = [mentor["user_id"] for mentor in paginated_mentor_details]
        users_result = supabase.table("users").select("user_id, full_name, email, role, created_at, updated_at").in_("user_id", user_ids).execute()
        users_lookup = {user["user_id"]: user for user in users_result.data or []}
        
        # Combine mentor details with user details
        mentors_list = []
        for mentor_detail in paginated_mentor_details:
            user_detail = users_lookup.get(mentor_detail["user_id"])
            mentors_list.append({
                "mentor_details": mentor_detail,
                "user_details": user_detail
            })
        
        # Create paginated response
        paginated_response = PaginatedResponse(
            items=mentors_list,
            total=total,
            page=page,
            size=size
        )
        
        return paginated_response.dict()
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in get_all_mentors_for_admin: {str(e)}")
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

# Admin Status Check Endpoint
@router.get("/check-status", response_model=dict)
async def check_admin_status(
    current_user = Depends(get_current_user)
):
    """
    Check if the current user is an admin (returns admin status without requiring admin access)
    """
    try:
        # Get user_id from current_user
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        
        if not user_id:
            return {
                "is_admin": False,
                "message": "Invalid user token"
            }
        
        # Check if user is an admin
        is_admin = await admin_service.is_admin_user(user_id)
        
        if is_admin:
            # Get admin account details
            admin_account = await admin_service.get_admin_account(user_id)
            return {
                "is_admin": True,
                "user_id": user_id,
                "admin_account_id": admin_account.id if admin_account else None,
                "email": admin_account.email if admin_account else None,
                "is_active": admin_account.is_active if admin_account else False,
                "message": "User is an admin"
            }
        else:
            return {
                "is_admin": False,
                "user_id": user_id,
                "message": "User is not an admin"
            }
            
    except Exception as e:
        return {
            "is_admin": False,
            "message": f"Error checking admin status: {str(e)}"
        }

# Admin Account Management Endpoints
@router.post("/accounts", response_model=AdminAccountResponse)
async def create_admin_account(
    admin_data: AdminAccountCreate,
    current_admin = Depends(get_current_admin)
):
    """
    Create a new admin account (only existing admins can create new admin accounts)
    """
    try:
        admin_account = await admin_service.create_admin_account(admin_data)
        return admin_account
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create admin account: {str(e)}"
        )

@router.get("/accounts", response_model=List[AdminAccountResponse])
async def get_all_admin_accounts(
    current_admin = Depends(get_current_admin)
):
    """
    Get all admin accounts (only admins can access this)
    """
    try:
        admin_accounts = await admin_service.get_all_admin_accounts()
        return admin_accounts
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch admin accounts: {str(e)}"
        )

# Mentor Verification Management Endpoints
@router.put("/mentors/{mentor_id}/verification", response_model=dict)
async def update_mentor_verification_status(
    mentor_id: str,
    verification_data: MentorVerificationUpdate,
    current_admin = Depends(get_current_admin)
):
    """
    Update mentor verification status (only admins can perform this action)
    """
    try:
        admin_user_id = current_admin["user_id"]
        
        success = await admin_service.update_mentor_verification_status(
            mentor_user_id=mentor_id,
            verification_data=verification_data,
            admin_user_id=admin_user_id
        )
        
        if success:
            # Send verification email if status is changed to "verified"
            if verification_data.verification_status.value == "verified":
                try:
                    # Get mentor details to send email
                    mentor_details = await mentor_service.get_mentor_details_by_user_id(mentor_id)
                    if mentor_details:
                        from app.services.email.email_service import email_service
                        user_name = f"{mentor_details.first_name} {mentor_details.last_name}"
                        email_result = email_service.send_mentor_verified_email(
                            to_email=mentor_details.email,
                            user_name=user_name
                        )
                        if email_result.get('success'):
                            logger.info(f"Verification email sent to mentor {mentor_details.email}")
                        else:
                            logger.warning(f"Failed to send verification email to mentor {mentor_details.email}: {email_result.get('message')}")
                except Exception as email_error:
                    logger.error(f"Error sending verification email to mentor {mentor_id}: {email_error}")
                    # Don't fail the verification update if email fails
            
            return {
                "success": True,
                "message": f"Mentor verification status updated to {verification_data.verification_status.value}",
                "mentor_id": mentor_id,
                "verification_status": verification_data.verification_status.value,
                "updated_by": admin_user_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update mentor verification status"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mentor verification status: {str(e)}"
        )


@router.get("/mentors/pending-verification", response_model=dict)
async def get_pending_verification_mentors(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)"),
    current_admin = Depends(get_current_admin)
):
    """
    Get mentors with pending verification status (only admins can access this)
    """
    try:
        supabase = get_supabase()
        
        # Get admin user IDs to exclude from pending verification list
        admin_accounts_result = supabase.table("admin_accounts").select("user_id").eq("is_active", True).execute()
        admin_user_ids = set()
        if admin_accounts_result.data:
            admin_user_ids = {admin["user_id"] for admin in admin_accounts_result.data}
        
        # Get mentors with pending verification status, excluding admin users
        offset = (page - 1) * size
        
        # First get all pending mentors
        all_pending_result = supabase.table("mentor_details").select(
            "*, users!mentor_details_user_id_fkey(user_id, full_name, email, created_at)"
        ).eq("verification_status", "pending").order("created_at", desc=True).execute()
        
        # Filter out admin users
        filtered_mentors = [
            mentor for mentor in all_pending_result.data 
            if mentor["user_id"] not in admin_user_ids
        ]
        
        # Apply pagination to filtered results
        total = len(filtered_mentors)
        mentors_page = filtered_mentors[offset:offset + size]
        
        mentors = []
        for mentor in mentors_page:
            user_data = mentor.get("users", {})
            mentors.append({
                "mentor_details": {
                    "user_id": mentor["user_id"],
                    "first_name": mentor["first_name"],
                    "last_name": mentor["last_name"],
                    "email": mentor["email"],
                    "university_associated": mentor["university_associated"],
                    "study_country": mentor["study_country"],
                    "education_level": mentor["education_level"],
                    "current_status": mentor["current_status"],
                    "verification_status": mentor["verification_status"],
                    "created_at": mentor["created_at"],
                    "updated_at": mentor["updated_at"]
                },
                "user_details": {
                    "user_id": user_data.get("user_id"),
                    "full_name": user_data.get("full_name"),
                    "email": user_data.get("email"),
                    "created_at": user_data.get("created_at")
                }
            })
        
        total_pages = (total + size - 1) // size
        
        return {
            "items": mentors,
            "pagination": {
                "total": total,
                "page": page,
                "size": size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending verification mentors: {str(e)}"
        )
