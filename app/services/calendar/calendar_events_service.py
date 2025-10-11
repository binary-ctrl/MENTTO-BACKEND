"""
Calendar Events Service for fetching and analyzing calendar data
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.database import get_supabase
from app.models.models import (
    CalendarEvent, TimeSlot, CalendarEventsResponse, 
    CalendarEventType, CalendarSyncRequest
)

logger = logging.getLogger(__name__)

class CalendarEventsService:
    def __init__(self):
        self.supabase = get_supabase()
    
    async def test_database_connection(self) -> bool:
        """Test database connection"""
        try:
            result = self.supabase.table("users").select("user_id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    async def get_user_calendar_events(
        self, 
        email: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_free_slots: bool = True,
        include_blocked_slots: bool = True
    ) -> CalendarEventsResponse:
        """Get calendar events and analyze free/blocked slots for a user"""
        start_time = datetime.utcnow()
        logger.info(f"Starting calendar events fetch for {email} at {start_time.isoformat()}")
        
        try:
            # Step 1: Validate input parameters
            logger.info(f"Validating input parameters for {email}")
            if not email or not email.strip():
                raise ValueError("Email cannot be empty")
            
            # Step 2: Get user's calendar credentials
            logger.info(f"Retrieving calendar credentials for {email}")
            credentials = await self._get_user_calendar_credentials(email)
            if not credentials:
                error_msg = f"No calendar credentials found for user: {email}"
                logger.error(error_msg)
                raise Exception(error_msg)

            logger.info(f"Successfully retrieved credentials for {email}")

            # Step 3: Set default date range if not provided
            if not start_date:
                start_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"Using default start_date: {start_date}")
            if not end_date:
                end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                logger.info(f"Using default end_date: {end_date}")

            logger.info(f"Fetching events from {start_date} to {end_date}")

            # Step 4: Fetch events from Google Calendar
            logger.info(f"Calling Google Calendar API for {email}")
            events = await self._fetch_google_calendar_events(
                credentials, start_date, end_date
            )

            logger.info(f"Retrieved {len(events)} events from Google Calendar for {email}")

            # Step 5: Analyze free and blocked slots
            free_slots = []
            blocked_slots = []
            
            if include_free_slots or include_blocked_slots:
                logger.info(f"Analyzing time slots for {email} - free_slots: {include_free_slots}, blocked_slots: {include_blocked_slots}")
                free_slots, blocked_slots = await self._analyze_time_slots(
                    events, start_date, end_date, include_free_slots, include_blocked_slots
                )

            # Step 6: Log completion statistics
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Calendar analysis complete for {email}: {len(free_slots)} free slots, {len(blocked_slots)} blocked slots, {len(events)} events in {duration:.2f}s")

            return CalendarEventsResponse(
                events=events,
                free_slots=free_slots,
                blocked_slots=blocked_slots,
                total_events=len(events),
                total_free_slots=len(free_slots),
                total_blocked_slots=len(blocked_slots),
                date_range={"start": start_date, "end": end_date}
            )

        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            logger.error(f"Error getting calendar events for {email} after {duration:.2f}s: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    async def _get_user_calendar_credentials(self, email: str) -> Optional[Credentials]:
        """Get calendar credentials for a user by email"""
        try:
            # Find user by email
            result = self.supabase.table("users").select(
                "user_id, google_calendar_credentials"
            ).eq("email", email).execute()

            if not result.data:
                logger.warning(f"User not found for email: {email}")
                return None

            user_data = result.data[0]
            credentials_data = user_data.get("google_calendar_credentials")

            if not credentials_data:
                logger.warning(f"No calendar credentials found for user: {email}")
                return None

            # Debug: Log the credentials data structure
            logger.info(f"Found credentials for {email}: {type(credentials_data)}")
            
            # Handle both dict and string formats
            if isinstance(credentials_data, str):
                import json
                try:
                    credentials_data = json.loads(credentials_data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in credentials for {email}")
                    return None

            # Create Google Credentials object
            credentials = Credentials(
                token=credentials_data.get("token"),
                refresh_token=credentials_data.get("refresh_token"),
                token_uri=credentials_data.get("token_uri"),
                client_id=credentials_data.get("client_id"),
                client_secret=credentials_data.get("client_secret"),
                scopes=credentials_data.get("scopes", [])
            )

            return credentials

        except Exception as e:
            logger.error(f"Error getting calendar credentials for {email}: {e}")
            return None

    async def _fetch_google_calendar_events(
        self, 
        credentials: Credentials, 
        start_date: str, 
        end_date: str
    ) -> List[CalendarEvent]:
        """Fetch events from Google Calendar with enhanced error handling"""
        try:
            logger.info(f"Building Google Calendar service for date range {start_date} to {end_date}")
            service = build('calendar', 'v3', credentials=credentials)
            
            # Convert date strings to datetime objects with validation
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                # Validate date range - allow same day (start_dt <= end_dt)
                if start_dt > end_dt:
                    raise ValueError(f"Start date {start_date} must be before or equal to end date {end_date}")
                
                # Check if date range is reasonable (not more than 1 year)
                if (end_dt - start_dt).days > 365:
                    logger.warning(f"Large date range requested: {(end_dt - start_dt).days} days")
                    
            except ValueError as ve:
                logger.error(f"Invalid date format: {ve}")
                raise ValueError(f"Invalid date format. Use YYYY-MM-DD format. Error: {ve}")
            
            logger.info(f"Fetching events from Google Calendar API")
            
            # Fetch events with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    events_result = service.events().list(
                        calendarId='primary',
                        timeMin=start_dt.isoformat() + 'Z',
                        timeMax=end_dt.isoformat() + 'Z',
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    break
                except HttpError as he:
                    if attempt == max_retries - 1:
                        logger.error(f"Google Calendar API error after {max_retries} attempts: {he}")
                        raise Exception(f"Failed to fetch calendar events after {max_retries} attempts: {he}")
                    else:
                        logger.warning(f"Google Calendar API error (attempt {attempt + 1}/{max_retries}): {he}")
                        continue

            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} raw events from Google Calendar")
            
            calendar_events = []
            parse_errors = 0

            for i, event in enumerate(events):
                try:
                    # Parse event data with error handling
                    start = event.get('start', {})
                    end = event.get('end', {})
                    
                    if not start or not end:
                        logger.warning(f"Event {i} missing start/end times, skipping")
                        parse_errors += 1
                        continue
                    
                    # Handle all-day events
                    if 'date' in start:
                        start_time = datetime.strptime(start['date'], '%Y-%m-%d')
                        end_time = datetime.strptime(end['date'], '%Y-%m-%d')
                        is_all_day = True
                    else:
                        if 'dateTime' not in start or 'dateTime' not in end:
                            logger.warning(f"Event {i} missing dateTime, skipping")
                            parse_errors += 1
                            continue
                            
                        start_time = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                        is_all_day = False

                    # Determine event type
                    event_type = self._determine_event_type(event)

                    # Parse created/updated times with fallback
                    try:
                        created_at = datetime.fromisoformat(event.get('created', '').replace('Z', '+00:00'))
                    except:
                        created_at = datetime.utcnow()
                        
                    try:
                        updated_at = datetime.fromisoformat(event.get('updated', '').replace('Z', '+00:00'))
                    except:
                        updated_at = datetime.utcnow()

                    calendar_event = CalendarEvent(
                        id=event.get('id', ''),
                        title=event.get('summary', 'No Title'),
                        start_time=start_time,
                        end_time=end_time,
                        description=event.get('description'),
                        location=event.get('location'),
                        event_type=event_type,
                        is_all_day=is_all_day,
                        attendees=[attendee.get('email', '') for attendee in event.get('attendees', [])],
                        created_at=created_at,
                        updated_at=updated_at
                    )
                    
                    calendar_events.append(calendar_event)
                    
                except Exception as parse_error:
                    logger.warning(f"Error parsing event {i}: {parse_error}")
                    parse_errors += 1
                    continue

            logger.info(f"Successfully parsed {len(calendar_events)} events, {parse_errors} parse errors")
            return calendar_events

        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            raise Exception(f"Failed to fetch calendar events: {e}")
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            raise

    def _determine_event_type(self, event: Dict[str, Any]) -> CalendarEventType:
        """Determine if an event is free, blocked, or busy"""
        try:
            # Check for free/busy status
            transparency = event.get('transparency', '')
            if transparency == 'transparent':
                return CalendarEventType.FREE
            
            # Check for "Out of Office" or "Busy" status
            summary = event.get('summary', '').lower()
            if any(keyword in summary for keyword in ['out of office', 'ooo', 'vacation', 'holiday']):
                return CalendarEventType.BLOCKED
            
            # Check for busy status in event details
            status = event.get('status', '')
            if status == 'confirmed':
                return CalendarEventType.BUSY
            
            # Default to busy for confirmed events
            return CalendarEventType.BUSY

        except Exception as e:
            logger.warning(f"Error determining event type: {e}")
            return CalendarEventType.BUSY

    async def _analyze_time_slots(
        self, 
        events: List[CalendarEvent], 
        start_date: str, 
        end_date: str,
        include_free_slots: bool = True,
        include_blocked_slots: bool = True
    ) -> Tuple[List[TimeSlot], List[TimeSlot]]:
        """Analyze calendar events to find free and blocked time slots"""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            free_slots = []
            blocked_slots = []
            
            # Group events by date
            events_by_date = {}
            for event in events:
                date_key = event.start_time.date()
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                events_by_date[date_key].append(event)
            
            # Analyze each day
            current_date = start_dt.date()
            while current_date <= end_dt.date():
                day_events = events_by_date.get(current_date, [])
                
                if include_free_slots:
                    day_free_slots = self._find_free_slots_for_day(current_date, day_events)
                    free_slots.extend(day_free_slots)
                
                if include_blocked_slots:
                    day_blocked_slots = self._find_blocked_slots_for_day(current_date, day_events)
                    blocked_slots.extend(day_blocked_slots)
                
                current_date += timedelta(days=1)
            
            return free_slots, blocked_slots

        except Exception as e:
            logger.error(f"Error analyzing time slots: {e}")
            return [], []

    def _find_free_slots_for_day(self, date, events: List[CalendarEvent]) -> List[TimeSlot]:
        """Find free time slots for a specific day"""
        try:
            # Define working hours (9 AM to 6 PM)
            work_start = time(9, 0)
            work_end = time(18, 0)
            
            # Create datetime objects for the day
            day_start = datetime.combine(date, work_start)
            day_end = datetime.combine(date, work_end)
            
            # Sort events by start time
            sorted_events = sorted(events, key=lambda x: x.start_time)
            
            free_slots = []
            current_time = day_start
            
            for event in sorted_events:
                # Skip events outside working hours
                if event.end_time <= day_start or event.start_time >= day_end:
                    continue
                
                # If there's a gap before this event, it's a free slot
                if current_time < event.start_time:
                    free_slot = TimeSlot(
                        start_time=current_time,
                        end_time=min(event.start_time, day_end),
                        is_available=True,
                        event_type=CalendarEventType.FREE
                    )
                    free_slots.append(free_slot)
                
                # Update current time to after this event
                current_time = max(current_time, event.end_time)
            
            # Check for free time after the last event
            if current_time < day_end:
                free_slot = TimeSlot(
                    start_time=current_time,
                    end_time=day_end,
                    is_available=True,
                    event_type=CalendarEventType.FREE
                )
                free_slots.append(free_slot)
            
            return free_slots

        except Exception as e:
            logger.error(f"Error finding free slots for {date}: {e}")
            return []

    def _find_blocked_slots_for_day(self, date, events: List[CalendarEvent]) -> List[TimeSlot]:
        """Find blocked time slots for a specific day"""
        try:
            blocked_slots = []
            
            for event in events:
                if event.event_type == CalendarEventType.BLOCKED:
                    blocked_slot = TimeSlot(
                        start_time=event.start_time,
                        end_time=event.end_time,
                        is_available=False,
                        event_title=event.title,
                        event_type=CalendarEventType.BLOCKED
                    )
                    blocked_slots.append(blocked_slot)
            
            return blocked_slots

        except Exception as e:
            logger.error(f"Error finding blocked slots for {date}: {e}")
            return []

    async def validate_calendar_data_integrity(self, email: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Validate calendar data integrity and provide detailed analysis"""
        try:
            logger.info(f"Starting calendar data integrity validation for {email}")
        
            validation_results = {
                "email": email,
                "validation_timestamp": datetime.utcnow().isoformat(),
                "date_range": {"start": start_date, "end": end_date},
                "validation_results": {}
            }
            
            # Test 1: Credentials Validation
            try:
                credentials = await self._get_user_calendar_credentials(email)
                validation_results["validation_results"]["credentials"] = {
                    "status": "success" if credentials else "failed",
                    "message": "Credentials found" if credentials else "No credentials found",
                    "has_credentials": bool(credentials)
                }
            except Exception as e:
                validation_results["validation_results"]["credentials"] = {
                    "status": "error",
                    "message": f"Credentials validation error: {str(e)}"
                }
            
            # Test 2: Data Fetching Validation
            try:
                if validation_results["validation_results"]["credentials"]["status"] == "success":
                    events = await self._fetch_google_calendar_events(credentials, start_date, end_date)
                    
                    # Analyze event data quality
                    total_events = len(events)
                    events_with_titles = len([e for e in events if e.title and e.title.strip()])
                    events_with_descriptions = len([e for e in events if e.description])
                    events_with_locations = len([e for e in events if e.location])
                    all_day_events = len([e for e in events if e.is_all_day])
                    
                    # Check for data anomalies
                    duplicate_titles = {}
                    for event in events:
                        if event.title in duplicate_titles:
                            duplicate_titles[event.title] += 1
                        else:
                            duplicate_titles[event.title] = 1
                    
                    duplicate_count = sum(1 for count in duplicate_titles.values() if count > 1)
                    
                    validation_results["validation_results"]["data_fetching"] = {
                        "status": "success",
                        "total_events": total_events,
                        "events_with_titles": events_with_titles,
                        "events_with_descriptions": events_with_descriptions,
                        "events_with_locations": events_with_locations,
                        "all_day_events": all_day_events,
                        "duplicate_titles": duplicate_count,
                        "data_quality_score": round((events_with_titles / total_events * 100) if total_events > 0 else 0, 2)
                    }
                else:
                    validation_results["validation_results"]["data_fetching"] = {
                        "status": "skipped",
                        "message": "Skipped due to missing credentials"
                    }
            except Exception as e:
                validation_results["validation_results"]["data_fetching"] = {
                    "status": "error",
                    "message": f"Data fetching validation error: {str(e)}"
                }
            
            # Test 3: Time Slot Analysis Validation
            try:
                if validation_results["validation_results"]["data_fetching"]["status"] == "success":
                    events = await self._fetch_google_calendar_events(credentials, start_date, end_date)
                    free_slots, blocked_slots = await self._analyze_time_slots(
                        events, start_date, end_date, True, True
                    )
                    
                    # Validate time slot logic
                    overlapping_slots = 0
                    invalid_slots = 0
                    
                    for slot in free_slots + blocked_slots:
                        if slot.start_time >= slot.end_time:
                            invalid_slots += 1
                    
                    validation_results["validation_results"]["time_slot_analysis"] = {
                        "status": "success",
                        "total_free_slots": len(free_slots),
                        "total_blocked_slots": len(blocked_slots),
                        "invalid_slots": invalid_slots,
                        "overlapping_slots": overlapping_slots,
                        "analysis_quality": "good" if invalid_slots == 0 else "needs_attention"
                    }
                else:
                    validation_results["validation_results"]["time_slot_analysis"] = {
                        "status": "skipped",
                        "message": "Skipped due to data fetching issues"
                    }
            except Exception as e:
                validation_results["validation_results"]["time_slot_analysis"] = {
                    "status": "error",
                    "message": f"Time slot analysis validation error: {str(e)}"
                }
            
            # Overall validation status
            failed_validations = [name for name, result in validation_results["validation_results"].items() 
                                 if result.get("status") == "error"]
            validation_results["overall_status"] = "success" if not failed_validations else "failed"
            validation_results["failed_validations"] = failed_validations
            
            logger.info(f"Calendar data integrity validation completed for {email}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Calendar data integrity validation failed for {email}: {e}")
            return {
                "email": email,
                "validation_timestamp": datetime.utcnow().isoformat(),
                "overall_status": "error",
                "error": str(e)
            }

    async def get_calendar_data_summary(self, email: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get a comprehensive summary of calendar data for a user"""
        try:
            logger.info(f"Generating calendar data summary for {email}")
            
            # Get calendar events
            events_result = await self.get_user_calendar_events(
                email=email,
                start_date=start_date,
                end_date=end_date,
                include_free_slots=True,
                include_blocked_slots=True
            )
            
            # Analyze event patterns
            events = events_result.events
            free_slots = events_result.free_slots
            blocked_slots = events_result.blocked_slots
            
            # Event type distribution
            event_types = {}
            for event in events:
                event_type = event.event_type.value
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            # Time distribution analysis
            hourly_distribution = {}
            for event in events:
                hour = event.start_time.hour
                hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
            
            # Day of week distribution
            weekday_distribution = {}
            for event in events:
                weekday = event.start_time.strftime('%A')
                weekday_distribution[weekday] = weekday_distribution.get(weekday, 0) + 1
            
            # Free time analysis
            total_free_hours = sum(
                (slot.end_time - slot.start_time).total_seconds() / 3600 
                for slot in free_slots
            )
            
            # Busy time analysis
            total_busy_hours = sum(
                (event.end_time - event.start_time).total_seconds() / 3600 
                for event in events if event.event_type.value != "free"
            )
            
            summary = {
                "email": email,
                "summary_timestamp": datetime.utcnow().isoformat(),
                "date_range": {"start": start_date, "end": end_date},
                "overview": {
                    "total_events": len(events),
                    "total_free_slots": len(free_slots),
                    "total_blocked_slots": len(blocked_slots),
                    "total_free_hours": round(total_free_hours, 2),
                    "total_busy_hours": round(total_busy_hours, 2),
                    "availability_percentage": round(
                        (total_free_hours / (total_free_hours + total_busy_hours) * 100) 
                        if (total_free_hours + total_busy_hours) > 0 else 0, 2
                    )
                },
                "event_analysis": {
                    "event_types": event_types,
                    "hourly_distribution": hourly_distribution,
                    "weekday_distribution": weekday_distribution
                },
                "data_quality": {
                    "events_with_titles": len([e for e in events if e.title and e.title.strip()]),
                    "events_with_descriptions": len([e for e in events if e.description]),
                    "events_with_locations": len([e for e in events if e.location]),
                    "all_day_events": len([e for e in events if e.is_all_day])
                }
            }
            
            logger.info(f"Calendar data summary generated for {email}: {len(events)} events, {len(free_slots)} free slots")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating calendar data summary for {email}: {e}")
            return {
                "email": email,
                "summary_timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }


# Create service instance
calendar_events_service = CalendarEventsService()
