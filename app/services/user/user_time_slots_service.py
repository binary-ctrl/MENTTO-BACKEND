"""
User Time Slots Service for managing user-created time slots
"""

import logging
from datetime import datetime, timedelta, time, timezone
from typing import List, Optional, Dict, Any
from app.core.database import get_supabase
from app.models.models import (
    UserTimeSlotCreate, UserTimeSlotUpdate, UserTimeSlotResponse,
    UserTimeSlotBulkCreate, UserTimeSlotBulkResponse, UserTimeSlotSummary,
    UserTimeSlotDayCreate, UserTimeSlotFlexibleCreate, UserTimeSlotWeeklyCreate, DaySlotConfig, TimeSlotStatus
)
from app.utils.timezone_utils import timezone_utils
import uuid

logger = logging.getLogger(__name__)

def _format_datetime_for_db(dt: datetime) -> str:
    """Format datetime for database storage with consistent microseconds"""
    # Convert to UTC if timezone-aware, otherwise assume UTC
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    
    # Ensure we have exactly 3 digits for milliseconds
    microseconds = dt.microsecond
    milliseconds = microseconds // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"

def _parse_datetime_from_db(dt_str: str) -> datetime:
    """Parse datetime string from database with flexible format handling"""
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        # Try parsing with Z suffix converted to +00:00
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
            return datetime.fromisoformat(dt_str)
        else:
            # Try to normalize the format by padding milliseconds to 3 digits
            import re
            # Match pattern like 2025-10-19T13:29:06.23+00:00
            pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d{1,3})([+-]\d{2}:\d{2})'
            match = re.match(pattern, dt_str)
            if match:
                base_time, milliseconds, timezone = match.groups()
                # Pad milliseconds to 3 digits
                milliseconds = milliseconds.ljust(3, '0')
                normalized_dt_str = f"{base_time}.{milliseconds}{timezone}"
                return datetime.fromisoformat(normalized_dt_str)
            else:
                raise ValueError(f"Unable to parse datetime string: {dt_str}")

class UserTimeSlotsService:
    def __init__(self):
        self.supabase = get_supabase()

    async def create_time_slot(self, user_id: str, slot_data: UserTimeSlotCreate) -> UserTimeSlotResponse:
        """Create a single time slot for a user"""
        try:
            # Validate time slot
            if slot_data.start_time >= slot_data.end_time:
                raise ValueError("Start time must be before end time")
            
            # Calculate duration
            duration = (slot_data.end_time - slot_data.start_time).total_seconds() / 60
            
            # Validate duration (should be 45 minutes by default, but allow flexibility)
            if duration <= 0:
                raise ValueError("Invalid slot duration")
            
            # Convert times to UTC for storage
            start_time_utc = timezone_utils.convert_to_utc(slot_data.start_time, slot_data.timezone)
            end_time_utc = timezone_utils.convert_to_utc(slot_data.end_time, slot_data.timezone)
            
            # Check for conflicts with existing slots
            await self._check_slot_conflicts(user_id, start_time_utc, end_time_utc)
            
            # Create slot data
            slot_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "start_time": _format_datetime_for_db(start_time_utc),
                "end_time": _format_datetime_for_db(end_time_utc),
                "timezone": slot_data.timezone,
                "title": slot_data.title,
                "description": slot_data.description,
                "status": TimeSlotStatus.AVAILABLE.value,
                "is_recurring": slot_data.is_recurring,
                "recurring_pattern": slot_data.recurring_pattern,
                "recurring_end_date": slot_data.recurring_end_date.isoformat() if slot_data.recurring_end_date else None,
                "duration_minutes": int(duration),
                "created_at": _format_datetime_for_db(datetime.utcnow()),
                "updated_at": _format_datetime_for_db(datetime.utcnow())
            }
            
            # Insert into database
            result = self.supabase.table("user_time_slots").insert(slot_record).execute()
            
            if not result.data:
                raise Exception("Failed to create time slot")
            
            # Get user details for response
            user_details = await self._get_user_details(user_id)
            
            # Convert back to user timezone for response
            start_time_local = timezone_utils.convert_from_utc(start_time_utc, slot_data.timezone)
            end_time_local = timezone_utils.convert_from_utc(end_time_utc, slot_data.timezone)
            
            return UserTimeSlotResponse(
                id=slot_record["id"],
                user_id=user_id,
                start_time=start_time_utc,
                end_time=end_time_utc,
                timezone=slot_data.timezone,
                title=slot_data.title,
                description=slot_data.description,
                status=TimeSlotStatus.AVAILABLE,
                is_recurring=slot_data.is_recurring,
                recurring_pattern=slot_data.recurring_pattern,
                recurring_end_date=slot_data.recurring_end_date,
                duration_minutes=int(duration),
                created_at=datetime.fromisoformat(slot_record["created_at"]),
                updated_at=datetime.fromisoformat(slot_record["updated_at"]),
                user_name=user_details.get("name"),
                user_email=user_details.get("email"),
                start_time_local=start_time_local.isoformat(),
                end_time_local=end_time_local.isoformat(),
                timezone_offset=timezone_utils.get_timezone_info(slot_data.timezone)['utc_offset']
            )
            
        except Exception as e:
            logger.error(f"Error creating time slot: {e}")
            raise

    async def create_bulk_time_slots(self, user_id: str, bulk_data: UserTimeSlotBulkCreate) -> UserTimeSlotBulkResponse:
        """Create multiple time slots for a user based on date range and days of week"""
        try:
            # Parse dates
            start_date = datetime.strptime(bulk_data.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(bulk_data.end_date, "%Y-%m-%d").date()
            
            # Parse times
            start_time = datetime.strptime(bulk_data.start_time, "%H:%M").time()
            end_time = datetime.strptime(bulk_data.end_time, "%H:%M").time()
            
            # Validate date range
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")
            
            # Validate time range
            if start_time >= end_time:
                raise ValueError("Start time must be before end time")
            
            # Validate slot duration
            if bulk_data.slot_duration_minutes <= 0:
                raise ValueError("Slot duration must be positive")
            
            # Generate slots
            slots_to_create = []
            current_date = start_date
            
            while current_date <= end_date:
                # Check if current day is in the selected days of week
                day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
                if day_of_week in bulk_data.days_of_week:
                    # Create slots for this day
                    current_datetime = datetime.combine(current_date, start_time)
                    end_datetime = datetime.combine(current_date, end_time)
                    
                    # Create slots in the specified duration
                    slot_start = current_datetime
                    while slot_start < end_datetime:
                        slot_end = slot_start + timedelta(minutes=bulk_data.slot_duration_minutes)
                        
                        # Don't exceed the end time
                        if slot_end > end_datetime:
                            break
                        
                        # Convert to UTC for storage
                        slot_start_utc = timezone_utils.convert_to_utc(slot_start, bulk_data.timezone)
                        slot_end_utc = timezone_utils.convert_to_utc(slot_end, bulk_data.timezone)
                        
                        # Check for conflicts
                        try:
                            await self._check_slot_conflicts(user_id, slot_start_utc, slot_end_utc)
                            
                            slot_record = {
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "start_time": _format_datetime_for_db(slot_start_utc),
                                "end_time": _format_datetime_for_db(slot_end_utc),
                                "timezone": bulk_data.timezone,
                                "title": bulk_data.title,
                                "description": bulk_data.description,
                                "status": TimeSlotStatus.AVAILABLE.value,
                                "is_recurring": False,
                                "recurring_pattern": None,
                                "recurring_end_date": None,
                                "duration_minutes": bulk_data.slot_duration_minutes,
                                "created_at": _format_datetime_for_db(datetime.utcnow()),
                                "updated_at": _format_datetime_for_db(datetime.utcnow())
                            }
                            
                            slots_to_create.append(slot_record)
                            
                        except ValueError as conflict_error:
                            logger.warning(f"Skipping conflicting slot: {conflict_error}")
                        
                        # Move to next slot
                        slot_start = slot_end
                
                current_date += timedelta(days=1)
            
            if not slots_to_create:
                raise ValueError("No valid slots could be created")
            
            # Insert all slots
            result = self.supabase.table("user_time_slots").insert(slots_to_create).execute()
            
            if not result.data:
                raise Exception("Failed to create time slots")
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            # Convert to response format
            created_slots = []
            for slot_data in result.data:
                start_time_utc = datetime.fromisoformat(slot_data["start_time"])
                end_time_utc = datetime.fromisoformat(slot_data["end_time"])
                
                start_time_local = timezone_utils.convert_from_utc(start_time_utc, bulk_data.timezone)
                end_time_local = timezone_utils.convert_from_utc(end_time_utc, bulk_data.timezone)
                
                created_slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    start_time=start_time_utc,
                    end_time=end_time_utc,
                    timezone=bulk_data.timezone,
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    start_time_local=start_time_local.isoformat(),
                    end_time_local=end_time_local.isoformat(),
                    timezone_offset=timezone_utils.get_timezone_info(bulk_data.timezone)['utc_offset']
                ))
            
            return UserTimeSlotBulkResponse(
                success=True,
                message=f"Successfully created {len(created_slots)} time slots",
                slots_created=len(created_slots),
                slots=created_slots,
                date_range={"start": bulk_data.start_date, "end": bulk_data.end_date},
                timezone=bulk_data.timezone
            )
            
        except Exception as e:
            logger.error(f"Error creating bulk time slots: {e}")
            raise

    async def create_day_time_slots(self, user_id: str, day_data: UserTimeSlotDayCreate) -> UserTimeSlotBulkResponse:
        """Create multiple time slots for a specific day"""
        try:
            # Parse date
            target_date = datetime.strptime(day_data.date, "%Y-%m-%d").date()
            
            # Validate date is not in the past
            if target_date < datetime.now().date():
                raise ValueError("Cannot create slots for past dates")
            
            # Validate time slots
            if not day_data.time_slots:
                raise ValueError("At least one time slot must be provided")
            
            # Generate slots
            slots_to_create = []
            
            for slot_info in day_data.time_slots:
                # Parse start and end times
                start_time_str = slot_info.get("start_time")
                end_time_str = slot_info.get("end_time")
                
                if not start_time_str or not end_time_str:
                    raise ValueError("Each time slot must have start_time and end_time")
                
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
                
                # Validate time range
                if start_time >= end_time:
                    raise ValueError(f"Start time {start_time_str} must be before end time {end_time_str}")
                
                # Create datetime objects for the target date
                slot_start_datetime = datetime.combine(target_date, start_time)
                slot_end_datetime = datetime.combine(target_date, end_time)
                
                # Convert to UTC for storage
                slot_start_utc = timezone_utils.convert_to_utc(slot_start_datetime, day_data.timezone)
                slot_end_utc = timezone_utils.convert_to_utc(slot_end_datetime, day_data.timezone)
                
                # Check for conflicts
                try:
                    await self._check_slot_conflicts(user_id, slot_start_utc, slot_end_utc)
                    
                    # Calculate duration
                    duration = (slot_end_utc - slot_start_utc).total_seconds() / 60
                    
                    slot_record = {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "start_time": _format_datetime_for_db(slot_start_utc),
                        "end_time": _format_datetime_for_db(slot_end_utc),
                        "timezone": day_data.timezone,
                        "title": day_data.title,
                        "description": day_data.description,
                        "status": TimeSlotStatus.AVAILABLE.value,
                        "is_recurring": False,
                        "recurring_pattern": None,
                        "recurring_end_date": None,
                        "duration_minutes": int(duration),
                        "created_at": _format_datetime_for_db(datetime.utcnow()),
                        "updated_at": _format_datetime_for_db(datetime.utcnow())
                    }
                    
                    slots_to_create.append(slot_record)
                    
                except ValueError as conflict_error:
                    logger.warning(f"Skipping conflicting slot {start_time_str}-{end_time_str}: {conflict_error}")
            
            if not slots_to_create:
                raise ValueError("No valid slots could be created due to conflicts")
            
            # Insert all slots
            result = self.supabase.table("user_time_slots").insert(slots_to_create).execute()
            
            if not result.data:
                raise Exception("Failed to create time slots")
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            # Convert to response format
            created_slots = []
            for slot_data in result.data:
                start_time_utc = datetime.fromisoformat(slot_data["start_time"])
                end_time_utc = datetime.fromisoformat(slot_data["end_time"])
                
                start_time_local = timezone_utils.convert_from_utc(start_time_utc, day_data.timezone)
                end_time_local = timezone_utils.convert_from_utc(end_time_utc, day_data.timezone)
                
                created_slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    start_time=start_time_utc,
                    end_time=end_time_utc,
                    timezone=day_data.timezone,
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    start_time_local=start_time_local.isoformat(),
                    end_time_local=end_time_local.isoformat(),
                    timezone_offset=timezone_utils.get_timezone_info(day_data.timezone)['utc_offset']
                ))
            
            return UserTimeSlotBulkResponse(
                success=True,
                message=f"Successfully created {len(created_slots)} time slots for {day_data.date}",
                slots_created=len(created_slots),
                slots=created_slots,
                date_range={"start": day_data.date, "end": day_data.date},
                timezone=day_data.timezone
            )
            
        except Exception as e:
            logger.error(f"Error creating day time slots: {e}")
            raise

    async def create_flexible_time_slots(self, user_id: str, flexible_data: UserTimeSlotFlexibleCreate) -> UserTimeSlotBulkResponse:
        """Create time slots with flexible configuration for different days of the week"""
        try:
            # Parse dates
            start_date = datetime.strptime(flexible_data.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(flexible_data.end_date, "%Y-%m-%d").date()
            
            # Validate date range
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")
            
            if start_date < datetime.now().date():
                raise ValueError("Cannot create slots for past dates")
            
            if (end_date - start_date).days > 90:
                raise ValueError("Date range cannot exceed 90 days")
            
            # Validate day configurations
            if not flexible_data.day_configs:
                raise ValueError("At least one day configuration must be provided")
            
            # Create a map of day configurations
            day_config_map = {}
            for config in flexible_data.day_configs:
                if config.day_of_week in day_config_map:
                    raise ValueError(f"Duplicate configuration for day {config.day_of_week}")
                day_config_map[config.day_of_week] = config
            
            # Generate slots
            slots_to_create = []
            current_date = start_date
            
            while current_date <= end_date:
                day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
                
                # Check if we have configuration for this day
                if day_of_week in day_config_map:
                    config = day_config_map[day_of_week]
                    
                    # Parse start and end times
                    start_time = datetime.strptime(config.start_time, "%H:%M").time()
                    end_time = datetime.strptime(config.end_time, "%H:%M").time()
                    
                    # Validate time range
                    if start_time >= end_time:
                        raise ValueError(f"Start time {config.start_time} must be before end time {config.end_time} for day {day_of_week}")
                    
                    # Calculate total time available
                    total_minutes = (datetime.combine(current_date, end_time) - datetime.combine(current_date, start_time)).total_seconds() / 60
                    required_minutes = (config.number_of_slots * config.slot_duration_minutes) + ((config.number_of_slots - 1) * config.break_between_slots_minutes)
                    
                    if total_minutes < required_minutes:
                        logger.warning(f"Not enough time for {config.number_of_slots} slots on {current_date} (day {day_of_week})")
                        current_date += timedelta(days=1)
                        continue
                    
                    # Create slots for this day
                    current_slot_start = datetime.combine(current_date, start_time)
                    
                    for slot_num in range(config.number_of_slots):
                        # Calculate slot end time
                        slot_end = current_slot_start + timedelta(minutes=config.slot_duration_minutes)
                        
                        # Convert to UTC for storage
                        slot_start_utc = timezone_utils.convert_to_utc(current_slot_start, flexible_data.timezone)
                        slot_end_utc = timezone_utils.convert_to_utc(slot_end, flexible_data.timezone)
                        
                        # Check for conflicts
                        try:
                            await self._check_slot_conflicts(user_id, slot_start_utc, slot_end_utc)
                            
                            slot_record = {
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "start_time": _format_datetime_for_db(slot_start_utc),
                                "end_time": _format_datetime_for_db(slot_end_utc),
                                "timezone": flexible_data.timezone,
                                "title": flexible_data.title,
                                "description": flexible_data.description,
                                "status": TimeSlotStatus.AVAILABLE.value,
                                "is_recurring": False,
                                "recurring_pattern": None,
                                "recurring_end_date": None,
                                "duration_minutes": config.slot_duration_minutes,
                                "created_at": _format_datetime_for_db(datetime.utcnow()),
                                "updated_at": _format_datetime_for_db(datetime.utcnow())
                            }
                            
                            slots_to_create.append(slot_record)
                            
                        except ValueError as conflict_error:
                            logger.warning(f"Skipping conflicting slot on {current_date}: {conflict_error}")
                        
                        # Move to next slot (add break time)
                        current_slot_start = slot_end + timedelta(minutes=config.break_between_slots_minutes)
                
                current_date += timedelta(days=1)
            
            if not slots_to_create:
                raise ValueError("No valid slots could be created")
            
            # Insert all slots
            result = self.supabase.table("user_time_slots").insert(slots_to_create).execute()
            
            if not result.data:
                raise Exception("Failed to create flexible time slots")
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            # Convert to response format
            created_slots = []
            for slot_data in result.data:
                start_time_utc = datetime.fromisoformat(slot_data["start_time"])
                end_time_utc = datetime.fromisoformat(slot_data["end_time"])
                
                start_time_local = timezone_utils.convert_from_utc(start_time_utc, flexible_data.timezone)
                end_time_local = timezone_utils.convert_from_utc(end_time_utc, flexible_data.timezone)
                
                created_slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    start_time=start_time_utc,
                    end_time=end_time_utc,
                    timezone=flexible_data.timezone,
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    start_time_local=start_time_local.isoformat(),
                    end_time_local=end_time_local.isoformat(),
                    timezone_offset=timezone_utils.get_timezone_info(flexible_data.timezone)['utc_offset']
                ))
            
            return UserTimeSlotBulkResponse(
                success=True,
                message=f"Successfully created {len(created_slots)} flexible time slots",
                slots_created=len(created_slots),
                slots=created_slots,
                date_range={"start": flexible_data.start_date, "end": flexible_data.end_date},
                timezone=flexible_data.timezone
            )
            
        except Exception as e:
            logger.error(f"Error creating flexible time slots: {e}")
            raise

    async def create_weekly_time_slots(self, user_id: str, weekly_data: UserTimeSlotWeeklyCreate) -> UserTimeSlotBulkResponse:
        """Create weekly recurring time slots with simplified structure"""
        try:
            # Validate day configurations
            if not weekly_data.day_configs:
                raise ValueError("At least one day configuration must be provided")
            
            # Check for duplicate day configurations
            day_config_map = {}
            for config in weekly_data.day_configs:
                if config.day_of_week in day_config_map:
                    raise ValueError(f"Duplicate configuration for day {config.day_of_week}")
                day_config_map[config.day_of_week] = config
            
            # Check for existing slots that might conflict
            existing_slots = await self._get_existing_weekly_slots(user_id)
            
            # Create slots for each day configuration
            slots_to_create = []
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for config in weekly_data.day_configs:
                # Check if slot already exists for this day and time
                existing_slot = self._find_conflicting_slot(existing_slots, config.day_of_week, config.start_time, config.end_time)
                if existing_slot:
                    logger.warning(f"Slot already exists for {day_names[config.day_of_week]} {config.start_time}-{config.end_time}")
                    continue
                
                # Calculate duration in minutes
                start_time_obj = datetime.strptime(config.start_time, "%H:%M").time()
                end_time_obj = datetime.strptime(config.end_time, "%H:%M").time()
                duration_minutes = int((datetime.combine(datetime.today(), end_time_obj) - datetime.combine(datetime.today(), start_time_obj)).total_seconds() / 60)
                
                logger.info(f"Creating weekly slot for {day_names[config.day_of_week]} from {config.start_time} to {config.end_time}")
                
                slot_record = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "day_of_week": config.day_of_week,
                    "start_time": config.start_time,
                    "end_time": config.end_time,
                    "timezone": weekly_data.timezone,
                    "title": weekly_data.title,
                    "description": weekly_data.description,
                    "status": TimeSlotStatus.AVAILABLE.value,
                    "is_recurring": True,
                    "recurring_pattern": "weekly",
                    "duration_minutes": duration_minutes,
                    "created_at": _format_datetime_for_db(datetime.utcnow()),
                    "updated_at": _format_datetime_for_db(datetime.utcnow())
                }
                
                slots_to_create.append(slot_record)
            
            if not slots_to_create:
                raise ValueError("No new slots could be created (all may already exist)")
            
            # Insert all slots
            result = self.supabase.table("user_time_slots").insert(slots_to_create).execute()
            
            if not result.data:
                raise Exception("Failed to create weekly time slots")
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            # Convert to response format
            created_slots = []
            for slot_data in result.data:
                created_slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    day_of_week=slot_data["day_of_week"],
                    start_time=slot_data["start_time"],
                    end_time=slot_data["end_time"],
                    timezone=slot_data["timezone"],
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    day_name=day_names[slot_data["day_of_week"]]
                ))
            
            return UserTimeSlotBulkResponse(
                success=True,
                message=f"Successfully created {len(created_slots)} weekly recurring time slots",
                slots_created=len(created_slots),
                slots=created_slots,
                date_range={"start": "Weekly", "end": "Recurring"},
                timezone=weekly_data.timezone
            )
            
        except Exception as e:
            logger.error(f"Error creating weekly time slots: {e}")
            raise

    async def get_user_time_slots(
        self, 
        user_id: str, 
        day_of_week: Optional[int] = None,
        status: Optional[TimeSlotStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserTimeSlotResponse]:
        """Get weekly recurring time slots for a user with optional filtering"""
        try:
            query = self.supabase.table("user_time_slots").select("*").eq("user_id", user_id)
            
            # Apply filters
            if day_of_week is not None:
                query = query.eq("day_of_week", day_of_week)
            
            if status:
                query = query.eq("status", status.value)
            
            # Apply pagination and ordering
            query = query.order("day_of_week", desc=False).order("start_time", desc=False).range(offset, offset + limit - 1)
            
            result = query.execute()
            
            if not result.data:
                return []
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            # Convert to response format
            slots = []
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for slot_data in result.data:
                slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    day_of_week=slot_data["day_of_week"],
                    start_time=slot_data["start_time"],
                    end_time=slot_data["end_time"],
                    timezone=slot_data["timezone"],
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    day_name=day_names[slot_data["day_of_week"]]
                ))
            
            return slots
            
        except Exception as e:
            logger.error(f"Error getting user time slots: {e}")
            raise

    async def update_time_slot(self, user_id: str, slot_id: str, update_data: UserTimeSlotUpdate) -> UserTimeSlotResponse:
        """Update a time slot"""
        try:
            # Get existing slot
            existing_slot = await self.get_time_slot_by_id(user_id, slot_id)
            if not existing_slot:
                raise ValueError("Time slot not found")
            
            # Prepare update data
            update_dict = {"updated_at": _format_datetime_for_db(datetime.utcnow())}
            
            if update_data.start_time is not None:
                update_dict["start_time"] = _format_datetime_for_db(update_data.start_time)
            
            if update_data.end_time is not None:
                update_dict["end_time"] = _format_datetime_for_db(update_data.end_time)
            
            if update_data.timezone is not None:
                update_dict["timezone"] = update_data.timezone
            
            if update_data.title is not None:
                update_dict["title"] = update_data.title
            
            if update_data.description is not None:
                update_dict["description"] = update_data.description
            
            if update_data.status is not None:
                update_dict["status"] = update_data.status.value
            
            if update_data.is_recurring is not None:
                update_dict["is_recurring"] = update_data.is_recurring
            
            if update_data.recurring_pattern is not None:
                update_dict["recurring_pattern"] = update_data.recurring_pattern
            
            if update_data.recurring_end_date is not None:
                update_dict["recurring_end_date"] = update_data.recurring_end_date.isoformat()
            
            # If times are being updated, check for conflicts
            if update_data.start_time is not None or update_data.end_time is not None:
                start_time = update_data.start_time if update_data.start_time else existing_slot.start_time
                end_time = update_data.end_time if update_data.end_time else existing_slot.end_time
                timezone = update_data.timezone if update_data.timezone else existing_slot.timezone
                
                # Convert to UTC
                start_time_utc = timezone_utils.convert_to_utc(start_time, timezone)
                end_time_utc = timezone_utils.convert_to_utc(end_time, timezone)
                
                # Check for conflicts (excluding current slot)
                await self._check_slot_conflicts(user_id, start_time_utc, end_time_utc, exclude_slot_id=slot_id)
                
                update_dict["start_time"] = _format_datetime_for_db(start_time_utc)
                update_dict["end_time"] = _format_datetime_for_db(end_time_utc)
                
                # Recalculate duration
                duration = (end_time_utc - start_time_utc).total_seconds() / 60
                update_dict["duration_minutes"] = int(duration)
            
            # Update in database
            result = self.supabase.table("user_time_slots").update(update_dict).eq("id", slot_id).eq("user_id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to update time slot")
            
            # Return updated slot
            return await self.get_time_slot_by_id(user_id, slot_id)
            
        except Exception as e:
            logger.error(f"Error updating time slot: {e}")
            raise

    async def delete_time_slot(self, user_id: str, slot_id: str) -> bool:
        """Delete a time slot"""
        try:
            result = self.supabase.table("user_time_slots").delete().eq("id", slot_id).eq("user_id", user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            logger.error(f"Error deleting time slot: {e}")
            raise

    async def get_time_slot_by_id(self, user_id: str, slot_id: str) -> Optional[UserTimeSlotResponse]:
        """Get a specific time slot by ID"""
        try:
            result = self.supabase.table("user_time_slots").select("*").eq("id", slot_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return None
            
            slot_data = result.data[0]
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            start_time_utc = datetime.fromisoformat(slot_data["start_time"])
            end_time_utc = datetime.fromisoformat(slot_data["end_time"])
            
            start_time_local = timezone_utils.convert_from_utc(start_time_utc, slot_data["timezone"])
            end_time_local = timezone_utils.convert_from_utc(end_time_utc, slot_data["timezone"])
            
            return UserTimeSlotResponse(
                id=slot_data["id"],
                user_id=user_id,
                start_time=start_time_utc,
                end_time=end_time_utc,
                timezone=slot_data["timezone"],
                title=slot_data["title"],
                description=slot_data["description"],
                status=TimeSlotStatus(slot_data["status"]),
                is_recurring=slot_data["is_recurring"],
                recurring_pattern=slot_data["recurring_pattern"],
                recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                duration_minutes=slot_data["duration_minutes"],
                created_at=datetime.fromisoformat(slot_data["created_at"]),
                updated_at=datetime.fromisoformat(slot_data["updated_at"]),
                user_name=user_details.get("name"),
                user_email=user_details.get("email"),
                start_time_local=start_time_local.isoformat(),
                end_time_local=end_time_local.isoformat(),
                timezone_offset=timezone_utils.get_timezone_info(slot_data["timezone"])['utc_offset']
            )
            
        except Exception as e:
            logger.error(f"Error getting time slot by ID: {e}")
            raise

    async def get_time_slot_summary(self, user_id: str) -> UserTimeSlotSummary:
        """Get summary of user's time slots"""
        try:
            # Get all slots for the user
            result = self.supabase.table("user_time_slots").select("*").eq("user_id", user_id).execute()
            
            if not result.data:
                return UserTimeSlotSummary(
                    total_slots=0,
                    available_slots=0,
                    booked_slots=0,
                    blocked_slots=0,
                    upcoming_slots=0,
                    next_available_slot=None,
                    recent_slots=[]
                )
            
            now = datetime.utcnow()
            total_slots = len(result.data)
            available_slots = 0
            booked_slots = 0
            blocked_slots = 0
            upcoming_slots = 0
            next_available_slot = None
            recent_slots = []
            
            # Get user details
            user_details = await self._get_user_details(user_id)
            
            for slot_data in result.data:
                start_time_utc = datetime.fromisoformat(slot_data["start_time"])
                status = TimeSlotStatus(slot_data["status"])
                
                # Count by status
                if status == TimeSlotStatus.AVAILABLE:
                    available_slots += 1
                elif status == TimeSlotStatus.BOOKED:
                    booked_slots += 1
                elif status == TimeSlotStatus.BLOCKED:
                    blocked_slots += 1
                
                # Count upcoming slots
                if start_time_utc > now:
                    upcoming_slots += 1
                    
                    # Find next available slot
                    if status == TimeSlotStatus.AVAILABLE and next_available_slot is None:
                        start_time_local = timezone_utils.convert_from_utc(start_time_utc, slot_data["timezone"])
                        end_time_utc = datetime.fromisoformat(slot_data["end_time"])
                        end_time_local = timezone_utils.convert_from_utc(end_time_utc, slot_data["timezone"])
                        
                        next_available_slot = UserTimeSlotResponse(
                            id=slot_data["id"],
                            user_id=user_id,
                            start_time=start_time_utc,
                            end_time=end_time_utc,
                            timezone=slot_data["timezone"],
                            title=slot_data["title"],
                            description=slot_data["description"],
                            status=status,
                            is_recurring=slot_data["is_recurring"],
                            recurring_pattern=slot_data["recurring_pattern"],
                            recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                            duration_minutes=slot_data["duration_minutes"],
                            created_at=datetime.fromisoformat(slot_data["created_at"]),
                            updated_at=datetime.fromisoformat(slot_data["updated_at"]),
                            user_name=user_details.get("name"),
                            user_email=user_details.get("email"),
                            start_time_local=start_time_local.isoformat(),
                            end_time_local=end_time_local.isoformat(),
                            timezone_offset=timezone_utils.get_timezone_info(slot_data["timezone"])['utc_offset']
                        )
            
            # Get recent slots (last 5)
            recent_result = self.supabase.table("user_time_slots").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
            
            for slot_data in recent_result.data:
                start_time_utc = datetime.fromisoformat(slot_data["start_time"])
                end_time_utc = datetime.fromisoformat(slot_data["end_time"])
                start_time_local = timezone_utils.convert_from_utc(start_time_utc, slot_data["timezone"])
                end_time_local = timezone_utils.convert_from_utc(end_time_utc, slot_data["timezone"])
                
                recent_slots.append(UserTimeSlotResponse(
                    id=slot_data["id"],
                    user_id=user_id,
                    start_time=start_time_utc,
                    end_time=end_time_utc,
                    timezone=slot_data["timezone"],
                    title=slot_data["title"],
                    description=slot_data["description"],
                    status=TimeSlotStatus(slot_data["status"]),
                    is_recurring=slot_data["is_recurring"],
                    recurring_pattern=slot_data["recurring_pattern"],
                    recurring_end_date=datetime.fromisoformat(slot_data["recurring_end_date"]) if slot_data["recurring_end_date"] else None,
                    duration_minutes=slot_data["duration_minutes"],
                    created_at=_parse_datetime_from_db(slot_data["created_at"]),
                    updated_at=_parse_datetime_from_db(slot_data["updated_at"]),
                    user_name=user_details.get("name"),
                    user_email=user_details.get("email"),
                    start_time_local=start_time_local.isoformat(),
                    end_time_local=end_time_local.isoformat(),
                    timezone_offset=timezone_utils.get_timezone_info(slot_data["timezone"])['utc_offset']
                ))
            
            return UserTimeSlotSummary(
                total_slots=total_slots,
                available_slots=available_slots,
                booked_slots=booked_slots,
                blocked_slots=blocked_slots,
                upcoming_slots=upcoming_slots,
                next_available_slot=next_available_slot,
                recent_slots=recent_slots
            )
            
        except Exception as e:
            logger.error(f"Error getting time slot summary: {e}")
            raise

    async def _check_slot_conflicts(self, user_id: str, start_time: datetime, end_time: datetime, exclude_slot_id: Optional[str] = None):
        """Check for conflicts with existing time slots"""
        try:
            query = self.supabase.table("user_time_slots").select("id, start_time, end_time").eq("user_id", user_id)
            
            if exclude_slot_id:
                query = query.neq("id", exclude_slot_id)
            
            result = query.execute()
            
            if not result.data:
                logger.info(f"No existing slots found for user {user_id}")
                return
            
            logger.info(f"Found {len(result.data)} existing slots for user {user_id}")
            
            for existing_slot in result.data:
                try:
                    # Handle different datetime formats from database
                    start_time_str = existing_slot["start_time"]
                    end_time_str = existing_slot["end_time"]
                    
                    # Parse datetime strings from database
                    existing_start = _parse_datetime_from_db(start_time_str)
                    existing_end = _parse_datetime_from_db(end_time_str)
                    
                    # Check for overlap
                    if (start_time < existing_end and end_time > existing_start):
                        logger.warning(f"Conflict detected: new slot {start_time} to {end_time} overlaps with existing slot {existing_start} to {existing_end}")
                        raise ValueError(f"Time slot conflicts with existing slot from {existing_start} to {existing_end}")
                except Exception as parse_error:
                    logger.error(f"Error parsing existing slot {existing_slot}: {parse_error}")
                    # Continue checking other slots even if one fails to parse
            
        except Exception as e:
            logger.error(f"Error checking slot conflicts: {e}")
            raise

    async def _get_existing_weekly_slots(self, user_id: str) -> List[Dict[str, Any]]:
        """Get existing weekly slots for a user"""
        try:
            result = self.supabase.table("user_time_slots").select("*").eq("user_id", user_id).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error getting existing weekly slots: {e}")
            return []
    
    def _find_conflicting_slot(self, existing_slots: List[Dict[str, Any]], day_of_week: int, start_time: str, end_time: str) -> Optional[Dict[str, Any]]:
        """Find if a slot already exists for the same day and time"""
        for slot in existing_slots:
            if (slot.get("day_of_week") == day_of_week and 
                slot.get("start_time") == start_time and 
                slot.get("end_time") == end_time):
                return slot
        return None

    async def _get_user_details(self, user_id: str) -> Dict[str, Any]:
        """Get user details for response"""
        try:
            result = self.supabase.table("users").select("name, email").eq("user_id", user_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                return {"name": None, "email": None}
                
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return {"name": None, "email": None}

# Service instance
user_time_slots_service = UserTimeSlotsService()
