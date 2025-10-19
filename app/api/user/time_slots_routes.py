"""
User Time Slots API routes
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import Optional, List
from datetime import datetime, timezone
import logging
from urllib.parse import unquote

from app.core.security.auth_dependencies import get_current_user
from app.services.user.user_time_slots_service import user_time_slots_service
from app.models.models import (
    UserResponse, UserTimeSlotCreate, UserTimeSlotUpdate, UserTimeSlotResponse,
    UserTimeSlotBulkCreate, UserTimeSlotBulkResponse, UserTimeSlotSummary,
    UserTimeSlotDayCreate, UserTimeSlotFlexibleCreate, UserTimeSlotWeeklyCreate, DaySlotConfig, TimeSlotStatus
)

router = APIRouter(prefix="/time-slots", tags=["user-time-slots"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=UserTimeSlotResponse)
async def create_time_slot(
    slot_data: UserTimeSlotCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a single time slot for the current user"""
    try:
        logger.info(f"Creating time slot for user {current_user.user_id}")
        
        # Validate that the slot is in the future
        if slot_data.start_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time slot must be in the future"
            )
        
        # Create the time slot
        created_slot = await user_time_slots_service.create_time_slot(
            user_id=str(current_user.user_id),
            slot_data=slot_data
        )
        
        return created_slot
        
    except ValueError as e:
        logger.warning(f"Validation error creating time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create time slot: {str(e)}"
        )

@router.post("/day", response_model=UserTimeSlotBulkResponse)
async def create_day_time_slots(
    day_data: UserTimeSlotDayCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create multiple time slots for a specific day"""
    try:
        logger.info(f"Creating day time slots for user {current_user.user_id} on {day_data.date}")
        
        # Validate date
        target_date = datetime.strptime(day_data.date, "%Y-%m-%d").date()
        
        if target_date < datetime.now().date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create slots for past dates"
            )
        
        # Validate time slots
        if not day_data.time_slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one time slot must be provided"
            )
        
        # Validate each time slot
        for i, slot_info in enumerate(day_data.time_slots):
            if not slot_info.get("start_time") or not slot_info.get("end_time"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Time slot {i+1} must have both start_time and end_time"
                )
        
        # Create the day time slots
        result = await user_time_slots_service.create_day_time_slots(
            user_id=str(current_user.user_id),
            day_data=day_data
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error creating day time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating day time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create day time slots: {str(e)}"
        )

@router.post("/flexible", response_model=UserTimeSlotBulkResponse)
async def create_flexible_time_slots(
    flexible_data: UserTimeSlotFlexibleCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create time slots with flexible configuration for different days of the week"""
    try:
        logger.info(f"Creating flexible time slots for user {current_user.user_id}")
        
        # Validate date range
        start_date = datetime.strptime(flexible_data.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(flexible_data.end_date, "%Y-%m-%d").date()
        
        if start_date < datetime.now().date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create slots for past dates"
            )
        
        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 90 days"
            )
        
        # Validate day configurations
        if not flexible_data.day_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one day configuration must be provided"
            )
        
        # Validate each day configuration
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for config in flexible_data.day_configs:
            if config.number_of_slots < 1 or config.number_of_slots > 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Number of slots for {day_names[config.day_of_week]} must be between 1 and 10"
                )
            
            if config.slot_duration_minutes not in [15, 30, 45, 60, 90, 120]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Slot duration for {day_names[config.day_of_week]} must be one of: 15, 30, 45, 60, 90, 120 minutes"
                )
        
        # Create the flexible time slots
        result = await user_time_slots_service.create_flexible_time_slots(
            user_id=str(current_user.user_id),
            flexible_data=flexible_data
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error creating flexible time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating flexible time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create flexible time slots: {str(e)}"
        )

@router.post("/weekly", response_model=UserTimeSlotBulkResponse)
async def create_weekly_time_slots(
    weekly_data: UserTimeSlotWeeklyCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create weekly recurring time slots based on days of the week"""
    try:
        logger.info(f"Creating weekly time slots for user {current_user.user_id}")
        
        # Validate day configurations
        if not weekly_data.day_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one day configuration must be provided"
            )
        
        # Validate each day configuration
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for config in weekly_data.day_configs:
            # Validate time format
            try:
                start_time = datetime.strptime(config.start_time, "%H:%M").time()
                end_time = datetime.strptime(config.end_time, "%H:%M").time()
                
                if start_time >= end_time:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Start time {config.start_time} must be before end time {config.end_time} for {day_names[config.day_of_week]}"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid time format for {day_names[config.day_of_week]}. Use HH:MM format (24-hour)"
                )
        
        # Create the weekly time slots
        result = await user_time_slots_service.create_weekly_time_slots(
            user_id=str(current_user.user_id),
            weekly_data=weekly_data
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error creating weekly time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating weekly time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create weekly time slots: {str(e)}"
        )

@router.post("/bulk", response_model=UserTimeSlotBulkResponse)
async def create_bulk_time_slots(
    bulk_data: UserTimeSlotBulkCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create multiple time slots for the current user based on date range and days of week"""
    try:
        logger.info(f"Creating bulk time slots for user {current_user.user_id}")
        
        # Validate date range
        start_date = datetime.strptime(bulk_data.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(bulk_data.end_date, "%Y-%m-%d").date()
        
        if start_date < datetime.now().date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date cannot be in the past"
            )
        
        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range cannot exceed 90 days"
            )
        
        # Validate days of week
        if not bulk_data.days_of_week or not all(0 <= day <= 6 for day in bulk_data.days_of_week):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Days of week must be integers between 0 (Monday) and 6 (Sunday)"
            )
        
        # Validate slot duration
        if bulk_data.slot_duration_minutes not in [15, 30, 45, 60, 90, 120]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slot duration must be one of: 15, 30, 45, 60, 90, 120 minutes"
            )
        
        # Create the bulk time slots
        result = await user_time_slots_service.create_bulk_time_slots(
            user_id=str(current_user.user_id),
            bulk_data=bulk_data
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error creating bulk time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating bulk time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bulk time slots: {str(e)}"
        )

@router.get("/", response_model=List[UserTimeSlotResponse])
async def get_time_slots(
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="Filter by day of week (0=Monday, 6=Sunday)"),
    status: Optional[TimeSlotStatus] = Query(None, description="Filter by slot status"),
    limit: int = Query(50, ge=1, le=100, description="Number of slots to return"),
    offset: int = Query(0, ge=0, description="Number of slots to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get weekly recurring time slots for the current user with optional filtering"""
    try:
        logger.info(f"Getting time slots for user {current_user.user_id}")
        
        # Get time slots
        slots = await user_time_slots_service.get_user_time_slots(
            user_id=str(current_user.user_id),
            day_of_week=day_of_week,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return slots
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting time slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get time slots: {str(e)}"
        )

@router.get("/user/{user_identifier}", response_model=List[UserTimeSlotResponse])
async def get_user_time_slots_by_identifier(
    user_identifier: str,
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="Filter by day of week (0=Monday, 6=Sunday)"),
    status: Optional[TimeSlotStatus] = Query(None, description="Filter by slot status"),
    limit: int = Query(50, ge=1, le=100, description="Number of slots to return"),
    offset: int = Query(0, ge=0, description="Number of slots to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get weekly recurring time slots for any user by email or user_id (public endpoint)"""
    try:
        logger.info(f"Getting time slots for user identifier: {user_identifier}")
        
        # Determine if user_identifier is an email or user_id
        user_id = None
        if "@" in user_identifier:
            # It's an email
            from app.services.user.services import user_service
            user = await user_service.get_user_by_email(user_identifier)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            user_id = str(user.user_id)
        else:
            # Assume it's a user_id
            user_id = user_identifier
        
        # Get time slots
        slots = await user_time_slots_service.get_user_time_slots(
            user_id=user_id,
            day_of_week=day_of_week,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return slots
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting time slots for user {user_identifier}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get time slots: {str(e)}"
        )

@router.get("/summary", response_model=UserTimeSlotSummary)
async def get_time_slot_summary(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get summary of the current user's time slots"""
    try:
        logger.info(f"Getting time slot summary for user {current_user.user_id}")
        
        summary = await user_time_slots_service.get_time_slot_summary(
            user_id=str(current_user.user_id)
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting time slot summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get time slot summary: {str(e)}"
        )

@router.get("/{slot_id}", response_model=UserTimeSlotResponse)
async def get_time_slot(
    slot_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific time slot by ID"""
    try:
        logger.info(f"Getting time slot {slot_id} for user {current_user.user_id}")
        
        slot = await user_time_slots_service.get_time_slot_by_id(
            user_id=str(current_user.user_id),
            slot_id=slot_id
        )
        
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time slot not found"
            )
        
        return slot
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get time slot: {str(e)}"
        )

@router.put("/{slot_id}", response_model=UserTimeSlotResponse)
async def update_time_slot(
    slot_id: str,
    update_data: UserTimeSlotUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update a time slot"""
    try:
        logger.info(f"Updating time slot {slot_id} for user {current_user.user_id}")
        
        # Validate that the slot is in the future if times are being updated
        if update_data.start_time and update_data.start_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Updated time slot must be in the future"
            )
        
        # Update the time slot
        updated_slot = await user_time_slots_service.update_time_slot(
            user_id=str(current_user.user_id),
            slot_id=slot_id,
            update_data=update_data
        )
        
        return updated_slot
        
    except ValueError as e:
        logger.warning(f"Validation error updating time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update time slot: {str(e)}"
        )

@router.delete("/{slot_id}")
async def delete_time_slot(
    slot_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a time slot"""
    try:
        logger.info(f"Deleting time slot {slot_id} for user {current_user.user_id}")
        
        success = await user_time_slots_service.delete_time_slot(
            user_id=str(current_user.user_id),
            slot_id=slot_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time slot not found"
            )
        
        return {"success": True, "message": "Time slot deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete time slot: {str(e)}"
        )

@router.get("/available/upcoming", response_model=List[UserTimeSlotResponse])
async def get_upcoming_available_slots(
    limit: int = Query(10, ge=1, le=50, description="Number of slots to return"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get upcoming available time slots for the current user"""
    try:
        logger.info(f"Getting upcoming available slots for user {current_user.user_id}")
        
        slots = await user_time_slots_service.get_user_time_slots(
            user_id=str(current_user.user_id),
            status=TimeSlotStatus.AVAILABLE,
            limit=limit,
            offset=0
        )
        
        # Filter to only future slots
        now = datetime.now()
        upcoming_slots = [slot for slot in slots if slot.start_time > now]
        
        return upcoming_slots[:limit]
        
    except Exception as e:
        logger.error(f"Error getting upcoming available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upcoming available slots: {str(e)}"
        )

@router.post("/{slot_id}/book")
async def book_time_slot(
    slot_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Book a time slot (change status to booked)"""
    try:
        logger.info(f"Booking time slot {slot_id} for user {current_user.user_id}")
        
        # Update slot status to booked
        update_data = UserTimeSlotUpdate(status=TimeSlotStatus.BOOKED)
        updated_slot = await user_time_slots_service.update_time_slot(
            user_id=str(current_user.user_id),
            slot_id=slot_id,
            update_data=update_data
        )
        
        return {
            "success": True,
            "message": "Time slot booked successfully",
            "slot": updated_slot
        }
        
    except ValueError as e:
        logger.warning(f"Validation error booking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error booking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book time slot: {str(e)}"
        )

@router.post("/{slot_id}/block")
async def block_time_slot(
    slot_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Block a time slot (change status to blocked)"""
    try:
        logger.info(f"Blocking time slot {slot_id} for user {current_user.user_id}")
        
        # Update slot status to blocked
        update_data = UserTimeSlotUpdate(status=TimeSlotStatus.BLOCKED)
        updated_slot = await user_time_slots_service.update_time_slot(
            user_id=str(current_user.user_id),
            slot_id=slot_id,
            update_data=update_data
        )
        
        return {
            "success": True,
            "message": "Time slot blocked successfully",
            "slot": updated_slot
        }
        
    except ValueError as e:
        logger.warning(f"Validation error blocking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to block time slot: {str(e)}"
        )

@router.post("/{slot_id}/unblock")
async def unblock_time_slot(
    slot_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Unblock a time slot (change status to available)"""
    try:
        logger.info(f"Unblocking time slot {slot_id} for user {current_user.user_id}")
        
        # Update slot status to available
        update_data = UserTimeSlotUpdate(status=TimeSlotStatus.AVAILABLE)
        updated_slot = await user_time_slots_service.update_time_slot(
            user_id=str(current_user.user_id),
            slot_id=slot_id,
            update_data=update_data
        )
        
        return {
            "success": True,
            "message": "Time slot unblocked successfully",
            "slot": updated_slot
        }
        
    except ValueError as e:
        logger.warning(f"Validation error unblocking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking time slot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unblock time slot: {str(e)}"
        )

@router.get("/mentor/{mentor_email}/available", response_model=List[UserTimeSlotResponse])
async def get_mentor_available_slots(
    mentor_email: str,
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    limit: int = Query(20, ge=1, le=50, description="Number of slots to return")
):
    """Get available time slots for a specific mentor (public endpoint)"""
    try:
        # Decode URL-encoded email
        mentor_email = unquote(mentor_email)
        logger.info(f"Getting available slots for mentor {mentor_email}")
        
        # Validate date format if provided
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start date must be in YYYY-MM-DD format"
                )
        
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="End date must be in YYYY-MM-DD format"
                )
        
        # Get mentor's user_id from email
        from app.services.user.services import user_service
        mentor_user = await user_service.get_user_by_email(mentor_email)
        
        if not mentor_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor not found"
            )
        
        # Get available time slots for the mentor
        slots = await user_time_slots_service.get_user_time_slots(
            user_id=str(mentor_user.user_id),
            start_date=start_date,
            end_date=end_date,
            status=TimeSlotStatus.AVAILABLE,
            limit=limit,
            offset=0
        )
        
        # Filter to only future slots (ensure timezone-aware comparison)
        now = datetime.now(timezone.utc)
        future_slots = [slot for slot in slots if slot.start_time > now]
        
        return future_slots[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mentor available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor available slots: {str(e)}"
        )

@router.get("/mentor/{mentor_email}/summary")
async def get_mentor_slots_summary(
    mentor_email: str
):
    """Get summary of mentor's time slots (public endpoint)"""
    try:
        # Decode URL-encoded email
        mentor_email = unquote(mentor_email)
        logger.info(f"Getting slots summary for mentor {mentor_email}")
        
        # Get mentor's user_id from email
        from app.services.user.services import user_service
        mentor_user = await user_service.get_user_by_email(mentor_email)
        
        if not mentor_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor not found"
            )
        
        # Get time slot summary for the mentor
        summary = await user_time_slots_service.get_time_slot_summary(
            user_id=str(mentor_user.user_id)
        )
        
        return {
            "mentor_email": mentor_email,
            "mentor_name": mentor_user.full_name,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mentor slots summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor slots summary: {str(e)}"
        )

@router.get("/mentor/{mentor_email}/debug")
async def debug_mentor_lookup(
    mentor_email: str
):
    """Debug endpoint to check mentor lookup"""
    try:
        # Decode URL-encoded email
        mentor_email = unquote(mentor_email)
        logger.info(f"Debug: Looking up mentor with email: {mentor_email}")
        
        # Import here to avoid circular imports
        from app.services.user.services import user_service
        
        # Try to get mentor by email
        mentor_user = await user_service.get_user_by_email(mentor_email)
        
        if mentor_user:
            return {
                "found": True,
                "mentor_email": mentor_email,
                "mentor_user_id": mentor_user.user_id,
                "mentor_name": mentor_user.full_name,
                "mentor_role": mentor_user.role
            }
        else:
            # Let's also check if there are any users with similar emails
            from app.core.database import get_supabase
            supabase = get_supabase()
            
            # Search for users with similar email patterns
            result = supabase.table("users").select("user_id, email, full_name, role").ilike("email", f"%{mentor_email.split('@')[0]}%").execute()
            
            return {
                "found": False,
                "searched_email": mentor_email,
                "similar_emails": result.data if result.data else [],
                "message": "Mentor not found, but here are similar emails"
            }
        
    except Exception as e:
        logger.error(f"Error in debug mentor lookup: {e}")
        return {
            "error": str(e),
            "searched_email": mentor_email
        }
