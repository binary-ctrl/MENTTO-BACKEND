"""
Batch Calendar Service for fetching free slots from multiple mentors
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.database import get_supabase
from app.models.models import (
    TimeSlot, CalendarEventType, MentorAvailability, 
    CommonSlot, BatchFreeSlotsResponse
)

logger = logging.getLogger(__name__)

class BatchCalendarService:
    def __init__(self):
        self.supabase = get_supabase()

    async def get_batch_free_slots(
        self, 
        mentor_emails: List[str],
        start_date: str,
        end_date: str,
        duration_minutes: int = 60
    ) -> BatchFreeSlotsResponse:
        """Get free slots for multiple mentors"""
        try:
            logger.info(f"Getting batch free slots for {len(mentor_emails)} mentors")
            
            # Set default date range if not provided
            if not start_date:
                start_date = datetime.now().strftime("%Y-%m-%d")
            if not end_date:
                end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

            # Get mentor details first
            mentor_details = await self._get_mentor_details(mentor_emails)
            
            # Create tasks for parallel processing
            tasks = []
            for email in mentor_emails:
                task = self._get_mentor_free_slots(
                    email, start_date, end_date, duration_minutes
                )
                tasks.append(task)
            
            # Execute all requests in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            mentors_availability = []
            for i, result in enumerate(results):
                email = mentor_emails[i]
                mentor_info = mentor_details.get(email, {})
                
                if isinstance(result, Exception):
                    logger.error(f"Error getting free slots for {email}: {result}")
                    # Add empty availability for failed requests
                    mentors_availability.append(MentorAvailability(
                        mentor_email=email,
                        mentor_name=mentor_info.get("name"),
                        mentor_id=mentor_info.get("user_id"),
                        free_slots=[],
                        total_free_slots=0
                    ))
                else:
                    mentors_availability.append(MentorAvailability(
                        mentor_email=email,
                        mentor_name=mentor_info.get("name"),
                        mentor_id=mentor_info.get("user_id"),
                        free_slots=result,
                        total_free_slots=len(result)
                    ))
            
            # Find common slots
            common_slots = self._find_common_slots(mentors_availability, duration_minutes)
            
            return BatchFreeSlotsResponse(
                mentors_availability=mentors_availability,
                common_slots=common_slots,
                total_mentors=len(mentor_emails),
                total_common_slots=len(common_slots),
                date_range={"start": start_date, "end": end_date},
                requested_duration_minutes=duration_minutes
            )

        except Exception as e:
            logger.error(f"Error in batch free slots: {e}")
            raise

    async def _get_mentor_details(self, mentor_emails: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get mentor details from database"""
        try:
            result = self.supabase.table("users").select(
                "user_id, email"
            ).in_("email", mentor_emails).execute()
            
            mentor_details = {}
            for user in result.data:
                email = user["email"]
                mentor_details[email] = {
                    "user_id": user["user_id"],
                    "name": email.split("@")[0],  # Use email prefix as name
                    "role": "mentor"  # Default role for testing
                }
            
            return mentor_details
            
        except Exception as e:
            logger.error(f"Error getting mentor details: {e}")
            return {}

    async def _get_mentor_free_slots(
        self, 
        email: str, 
        start_date: str, 
        end_date: str, 
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Get free slots for a single mentor"""
        try:
            # Get user's calendar credentials
            credentials = await self._get_user_calendar_credentials(email)
            if not credentials:
                logger.warning(f"No calendar credentials found for mentor: {email}")
                return []

            # Fetch events from Google Calendar
            events = await self._fetch_google_calendar_events(
                credentials, start_date, end_date
            )

            # Find free slots
            free_slots = self._find_free_slots_for_mentor(
                events, start_date, end_date, duration_minutes
            )

            return free_slots

        except Exception as e:
            logger.error(f"Error getting free slots for mentor {email}: {e}")
            return []

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
    ) -> List[Dict[str, Any]]:
        """Fetch events from Google Calendar"""
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Convert date strings to datetime objects
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Fetch events
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_dt.isoformat() + 'Z',
                timeMax=end_dt.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            return events_result.get('items', [])

        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return []

    def _find_free_slots_for_mentor(
        self, 
        events: List[Dict[str, Any]], 
        start_date: str, 
        end_date: str, 
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Find free time slots for a mentor"""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            free_slots = []
            
            # Group events by date
            events_by_date = {}
            for event in events:
                start = event.get('start', {})
                if 'dateTime' in start:
                    event_date = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00')).date()
                    if event_date not in events_by_date:
                        events_by_date[event_date] = []
                    events_by_date[event_date].append(event)
            
            # Analyze each day
            current_date = start_dt.date()
            while current_date <= end_dt.date():
                day_events = events_by_date.get(current_date, [])
                day_free_slots = self._find_free_slots_for_day(
                    current_date, day_events, duration_minutes
                )
                free_slots.extend(day_free_slots)
                current_date += timedelta(days=1)
            
            return free_slots

        except Exception as e:
            logger.error(f"Error finding free slots for mentor: {e}")
            return []

    def _find_free_slots_for_day(
        self, 
        date, 
        events: List[Dict[str, Any]], 
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Find free time slots for a specific day"""
        try:
            # Define working hours (9 AM to 6 PM)
            work_start = time(9, 0)
            work_end = time(18, 0)
            
            # Create datetime objects for the day
            day_start = datetime.combine(date, work_start)
            day_end = datetime.combine(date, work_end)
            
            # Sort events by start time
            sorted_events = sorted(events, key=lambda x: x.get('start', {}).get('dateTime', ''))
            
            free_slots = []
            current_time = day_start
            
            for event in sorted_events:
                start = event.get('start', {})
                end = event.get('end', {})
                
                if 'dateTime' in start:
                    event_start = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
                    
                    # Skip events outside working hours
                    if event_end <= day_start or event_start >= day_end:
                        continue
                    
                    # If there's a gap before this event, check if it's long enough
                    if current_time < event_start:
                        gap_duration = (event_start - current_time).total_seconds() / 60
                        if gap_duration >= duration_minutes:
                            free_slot = TimeSlot(
                                start_time=current_time,
                                end_time=min(event_start, day_end),
                                is_available=True,
                                event_type=CalendarEventType.FREE
                            )
                            free_slots.append(free_slot)
                    
                    # Update current time to after this event
                    current_time = max(current_time, event_end)
            
            # Check for free time after the last event
            if current_time < day_end:
                remaining_duration = (day_end - current_time).total_seconds() / 60
                if remaining_duration >= duration_minutes:
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

    def _find_common_slots(
        self, 
        mentors_availability: List[MentorAvailability], 
        duration_minutes: int
    ) -> List[CommonSlot]:
        """Find common time slots across multiple mentors"""
        try:
            if not mentors_availability:
                return []
            
            # Get all unique time slots
            all_slots = []
            for mentor in mentors_availability:
                for slot in mentor.free_slots:
                    all_slots.append({
                        'start_time': slot.start_time,
                        'end_time': slot.end_time,
                        'mentor_email': mentor.mentor_email
                    })
            
            # Group slots by time
            slot_groups = {}
            for slot in all_slots:
                time_key = f"{slot['start_time'].isoformat()}_{slot['end_time'].isoformat()}"
                if time_key not in slot_groups:
                    slot_groups[time_key] = {
                        'start_time': slot['start_time'],
                        'end_time': slot['end_time'],
                        'mentors': []
                    }
                slot_groups[time_key]['mentors'].append(slot['mentor_email'])
            
            # Find slots with multiple mentors
            common_slots = []
            for time_key, group in slot_groups.items():
                if len(group['mentors']) > 1:
                    common_slot = CommonSlot(
                        start_time=group['start_time'],
                        end_time=group['end_time'],
                        duration_minutes=duration_minutes,
                        available_mentors=group['mentors'],
                        available_mentor_count=len(group['mentors'])
                    )
                    common_slots.append(common_slot)
            
            # Sort by start time
            common_slots.sort(key=lambda x: x.start_time)
            
            return common_slots

        except Exception as e:
            logger.error(f"Error finding common slots: {e}")
            return []


# Create service instance
batch_calendar_service = BatchCalendarService()
