"""
Timezone utilities for handling global users
"""
import pytz
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class TimezoneUtils:
    """Utility class for timezone operations"""
    
    # Common timezones for the platform
    COMMON_TIMEZONES = {
        'IST': 'Asia/Kolkata',      # India
        'GMT': 'Europe/London',     # UK
        'EST': 'America/New_York',  # US East
        'PST': 'America/Los_Angeles', # US West
        'CET': 'Europe/Paris',     # Central Europe
        'JST': 'Asia/Tokyo',       # Japan
        'AEST': 'Australia/Sydney', # Australia
        'UTC': 'UTC'               # UTC
    }
    
    @staticmethod
    def get_user_timezone(user_timezone: str = None) -> str:
        """Get user's timezone, default to UTC if not provided"""
        if user_timezone and user_timezone in TimezoneUtils.COMMON_TIMEZONES.values():
            return user_timezone
        elif user_timezone and user_timezone in TimezoneUtils.COMMON_TIMEZONES:
            return TimezoneUtils.COMMON_TIMEZONES[user_timezone]
        else:
            logger.warning(f"Unknown timezone: {user_timezone}, defaulting to UTC")
            return 'UTC'
    
    @staticmethod
    def convert_to_utc(dt: datetime, from_timezone: str) -> datetime:
        """Convert datetime from user timezone to UTC"""
        try:
            if dt.tzinfo is None:
                # If datetime is naive, assume it's in the user's timezone
                user_tz = pytz.timezone(from_timezone)
                dt = user_tz.localize(dt)
            
            # Convert to UTC
            return dt.astimezone(pytz.UTC)
        except Exception as e:
            logger.error(f"Error converting to UTC: {e}")
            raise ValueError(f"Invalid timezone conversion: {e}")
    
    @staticmethod
    def convert_from_utc(dt: datetime, to_timezone: str) -> datetime:
        """Convert datetime from UTC to user timezone"""
        try:
            if dt.tzinfo is None:
                # If datetime is naive, assume it's UTC
                dt = pytz.UTC.localize(dt)
            
            # Convert to user timezone
            user_tz = pytz.timezone(to_timezone)
            return dt.astimezone(user_tz)
        except Exception as e:
            logger.error(f"Error converting from UTC: {e}")
            raise ValueError(f"Invalid timezone conversion: {e}")
    
    @staticmethod
    def convert_between_timezones(dt: datetime, from_tz: str, to_tz: str) -> datetime:
        """Convert datetime between two timezones"""
        try:
            if dt.tzinfo is None:
                # If datetime is naive, assume it's in the source timezone
                source_tz = pytz.timezone(from_tz)
                dt = source_tz.localize(dt)
            
            # Convert to target timezone
            target_tz = pytz.timezone(to_tz)
            return dt.astimezone(target_tz)
        except Exception as e:
            logger.error(f"Error converting between timezones: {e}")
            raise ValueError(f"Invalid timezone conversion: {e}")
    
    @staticmethod
    def get_timezone_info(timezone_name: str) -> Dict[str, Any]:
        """Get timezone information"""
        try:
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)
            
            return {
                'timezone': timezone_name,
                'utc_offset': now.strftime('%z'),
                'dst_active': now.dst().total_seconds() != 0,
                'current_time': now.isoformat(),
                'display_name': tz.zone
            }
        except Exception as e:
            logger.error(f"Error getting timezone info: {e}")
            return {
                'timezone': timezone_name,
                'error': str(e)
            }
    
    @staticmethod
    def format_datetime_for_timezone(dt: datetime, timezone_name: str, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        """Format datetime for specific timezone"""
        try:
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            user_tz = pytz.timezone(timezone_name)
            local_dt = dt.astimezone(user_tz)
            return local_dt.strftime(format_str)
        except Exception as e:
            logger.error(f"Error formatting datetime: {e}")
            return dt.isoformat()
    
    @staticmethod
    def get_available_timezones() -> List[Dict[str, str]]:
        """Get list of available timezones"""
        return [
            {'code': 'IST', 'name': 'India Standard Time', 'timezone': 'Asia/Kolkata'},
            {'code': 'GMT', 'name': 'Greenwich Mean Time', 'timezone': 'Europe/London'},
            {'code': 'EST', 'name': 'Eastern Standard Time', 'timezone': 'America/New_York'},
            {'code': 'PST', 'name': 'Pacific Standard Time', 'timezone': 'America/Los_Angeles'},
            {'code': 'CET', 'name': 'Central European Time', 'timezone': 'Europe/Paris'},
            {'code': 'JST', 'name': 'Japan Standard Time', 'timezone': 'Asia/Tokyo'},
            {'code': 'AEST', 'name': 'Australian Eastern Time', 'timezone': 'Australia/Sydney'},
            {'code': 'UTC', 'name': 'Coordinated Universal Time', 'timezone': 'UTC'}
        ]
    
    @staticmethod
    def create_timezone_aware_datetime(year: int, month: int, day: int, hour: int, minute: int, timezone_name: str) -> datetime:
        """Create timezone-aware datetime"""
        try:
            tz = pytz.timezone(timezone_name)
            return tz.localize(datetime(year, month, day, hour, minute))
        except Exception as e:
            logger.error(f"Error creating timezone-aware datetime: {e}")
            raise ValueError(f"Invalid datetime or timezone: {e}")

# Create utility instance
timezone_utils = TimezoneUtils()
