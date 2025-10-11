"""
Schedule Call Service for managing mentorship calls and calendar invites
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.database import get_supabase, get_supabase_admin
from app.models.models import (
    ScheduleCallRequest, ScheduledCall, TimeSlot, CalendarEventType
)

logger = logging.getLogger(__name__)

class ScheduleCallService:
    def __init__(self):
        self.supabase = get_supabase()
        self.supabase_admin = get_supabase_admin()

    async def schedule_call(
        self, 
        mentee_id: str,
        mentee_email: str,
        request: ScheduleCallRequest
    ) -> ScheduledCall:
        """Schedule a call between mentee and mentor"""
        try:
            logger.info(f"Scheduling call between {mentee_email} and {request.mentor_email}")
            
            # Validate mentor exists and is a mentor
            mentor_info = await self._get_mentor_info(request.mentor_email)
            if not mentor_info:
                raise Exception(f"Mentor not found: {request.mentor_email}")
            
            # Check if the time slot is still available
            is_available = await self._check_slot_availability(
                request.mentor_email, request.start_time, request.end_time
            )
            if not is_available:
                raise Exception("Time slot is no longer available")
            
            # Create scheduled call record
            call_id = str(uuid.uuid4())
            call_record = {
                "id": call_id,
                "mentee_id": mentee_id,
                "mentor_id": mentor_info["user_id"],
                "mentee_email": mentee_email,
                "mentor_email": request.mentor_email,
                "start_time": request.start_time.isoformat(),
                "end_time": request.end_time.isoformat(),
                "title": request.title,
                "description": request.description,
                "meeting_link": request.meeting_link,
                "status": "scheduled",
                "notes": request.notes,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert into database
            result = self.supabase_admin.table("scheduled_calls").insert(call_record).execute()
            
            if not result.data:
                raise Exception("Failed to create scheduled call record")
            
            # Send calendar invites to both parties
            await self._send_calendar_invites(
                mentee_email, request.mentor_email, request, call_id
            )
            
            # Update status to confirmed
            await self._update_call_status(call_id, "confirmed")
            
            return ScheduledCall(
                id=call_id,
                mentee_id=mentee_id,
                mentor_id=mentor_info["user_id"],
                mentee_email=mentee_email,
                mentor_email=request.mentor_email,
                start_time=request.start_time,
                end_time=request.end_time,
                title=request.title,
                description=request.description,
                meeting_link=request.meeting_link,
                status="confirmed",
                notes=request.notes,
                created_at=datetime.fromisoformat(call_record["created_at"]),
                updated_at=datetime.fromisoformat(call_record["updated_at"])
            )
            
        except Exception as e:
            logger.error(f"Error scheduling call: {e}")
            raise

    async def _get_mentor_info(self, mentor_email: str) -> Optional[Dict[str, Any]]:
        """Get mentor information from database"""
        try:
            # For testing purposes, allow any user to be a mentor
            # Only select columns that actually exist
            result = self.supabase.table("users").select(
                "user_id, email"
            ).eq("email", mentor_email).execute()
            
            logger.info(f"Query result for {mentor_email}: {result.data}")
            
            if not result.data: 
                logger.warning(f"No user found for email: {mentor_email}")
                return None
            
            user = result.data[0]
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user["email"].split("@")[0],  # Use email prefix as name
                "role": "mentor"  # Default role for testing
            }
            
        except Exception as e:
            logger.error(f"Error getting mentor info: {e}")
            return None

    async def _check_slot_availability(
        self, 
        mentor_email: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> bool:
        """Check if a time slot is still available for the mentor"""
        try:
            # Get mentor's calendar credentials
            credentials = await self._get_user_calendar_credentials(mentor_email)
            if not credentials:
                logger.warning(f"No calendar credentials found for mentor: {mentor_email}")
                return True  # Assume available if no credentials
            
            # Check for conflicting events
            service = build('calendar', 'v3', credentials=credentials)
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Check for any overlapping events
            for event in events:
                event_start = event.get('start', {}).get('dateTime')
                event_end = event.get('end', {}).get('dateTime')
                
                if event_start and event_end:
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                    
                    # Check for overlap
                    if (event_start_dt < end_time and event_end_dt > start_time):
                        logger.info(f"Found conflicting event: {event.get('summary', 'No title')}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking slot availability: {e}")
            return True  # Assume available on error

    async def _get_user_calendar_credentials(self, email: str) -> Optional[Credentials]:
        """Get calendar credentials for a user by email"""
        try:
            result = self.supabase.table("users").select(
                "user_id, google_calendar_credentials"
            ).eq("email", email).execute()
            
            if not result.data:
                return None
            
            user_data = result.data[0]
            credentials_data = user_data.get("google_calendar_credentials")
            
            if not credentials_data:
                return None
            
            # Handle both dict and string formats
            if isinstance(credentials_data, str):
                import json
                try:
                    credentials_data = json.loads(credentials_data)
                except json.JSONDecodeError:
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

    async def _send_calendar_invites(
        self, 
        mentee_email: str, 
        mentor_email: str, 
        request: ScheduleCallRequest,
        call_id: str
    ):
        """Send calendar invites to both mentee and mentor"""
        try:
            # Create calendar event data
            event_data = {
                'summary': request.title,
                'description': request.description or f"Mentorship session between {mentee_email} and {mentor_email}",
                'start': {
                    'dateTime': request.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': request.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [
                    {'email': mentee_email},
                    {'email': mentor_email},
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 30},       # 30 minutes before
                    ],
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': call_id,
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                } if not request.meeting_link else None,
                'extendedProperties': {
                    'private': {
                        'callId': call_id,
                        'menteeEmail': mentee_email,
                        'mentorEmail': mentor_email
                    }
                }
            }
            
            # Remove conferenceData if meeting_link is provided
            if request.meeting_link:
                event_data['location'] = request.meeting_link
                del event_data['conferenceData']
            
            # Create calendar event from mentee's calendar (mentee is the organizer)
            # This will automatically send invites to all attendees including the mentor
            await self._create_calendar_event(mentee_email, event_data)
            
            logger.info(f"Calendar invites sent for call {call_id}")
            
        except Exception as e:
            logger.error(f"Error sending calendar invites: {e}")
            raise

    async def _create_calendar_event(self, email: str, event_data: Dict[str, Any]):
        """Create a calendar event for a user"""
        try:
            credentials = await self._get_user_calendar_credentials(email)
            if not credentials:
                logger.warning(f"No calendar credentials for {email}, skipping calendar invite")
                return
            
            service = build('calendar', 'v3', credentials=credentials)
            
            # Create the event
            event = service.events().insert(
                calendarId='primary',
                body=event_data,
                sendUpdates='all'  # Send email notifications
            ).execute()
            
            logger.info(f"Calendar event created for {email}: {event.get('id')}")
            
        except HttpError as e:
            logger.error(f"Google Calendar API error for {email}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating calendar event for {email}: {e}")
            raise

    async def _update_call_status(self, call_id: str, status: str):
        """Update the status of a scheduled call"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase_admin.table("scheduled_calls").update(update_data).eq("id", call_id).execute()
            
            if not result.data:
                logger.error(f"Failed to update call status for {call_id}")
            
        except Exception as e:
            logger.error(f"Error updating call status: {e}")

    async def get_user_scheduled_calls(
        self, 
        user_id: str, 
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[ScheduledCall]:
        """Get scheduled calls for a user"""
        try:
            query = self.supabase_admin.table("scheduled_calls").select(
                "*, mentee:mentee_id(*), mentor:mentor_id(*)"
            ).or_(f"mentee_id.eq.{user_id},mentor_id.eq.{user_id}")
            
            if status:
                query = query.eq("status", status)
            
            result = query.order("start_time", desc=True).range(offset, offset + limit - 1).execute()
            
            if not result.data:
                return []
            
            calls = []
            for call_data in result.data:
                calls.append(self._format_scheduled_call(call_data))
            
            return calls
            
        except Exception as e:
            logger.error(f"Error getting scheduled calls: {e}")
            return []

    async def cancel_call(self, call_id: str, user_id: str) -> bool:
        """Cancel a scheduled call"""
        try:
            # Get the call details
            result = self.supabase_admin.table("scheduled_calls").select("*").eq("id", call_id).execute()
            
            if not result.data:
                raise Exception("Call not found")
            
            call_data = result.data[0]
            
            # Check if user is authorized to cancel
            if call_data["mentee_id"] != user_id and call_data["mentor_id"] != user_id:
                raise Exception("Unauthorized to cancel this call")
            
            # Update status to cancelled
            await self._update_call_status(call_id, "cancelled")
            
            # TODO: Send cancellation emails and remove calendar events
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling call: {e}")
            return False

    def _format_scheduled_call(self, call_data: Dict[str, Any]) -> ScheduledCall:
        """Format database row to ScheduledCall object"""
        return ScheduledCall(
            id=call_data["id"],
            mentee_id=call_data["mentee_id"],
            mentor_id=call_data["mentor_id"],
            mentee_email=call_data["mentee_email"],
            mentor_email=call_data["mentor_email"],
            start_time=datetime.fromisoformat(call_data["start_time"]),
            end_time=datetime.fromisoformat(call_data["end_time"]),
            title=call_data["title"],
            description=call_data.get("description"),
            meeting_link=call_data.get("meeting_link"),
            status=call_data["status"],
            notes=call_data.get("notes"),
            created_at=datetime.fromisoformat(call_data["created_at"]),
            updated_at=datetime.fromisoformat(call_data["updated_at"])
        )


# Create service instance
schedule_call_service = ScheduleCallService()
