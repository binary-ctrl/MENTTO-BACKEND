"""
Google Calendar Service for managing calendar events and availability
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import base64

from app.core.config import settings
from app.models.models import CalendarEventCreate, CalendarEventResponse, AvailabilitySlot, SendInvitationRequest

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

class GoogleCalendarService:
    def __init__(self):
        self.service = None
        self.credentials = None

    def get_authorization_url(self, user_id: str) -> str:
        """Get Google OAuth authorization URL for calendar access"""
        try:
            # Use calendar-specific redirect URI if available, otherwise fall back to general one
            calendar_redirect_uri = settings.google_calendar_redirect_uri or settings.google_redirect_uri
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [calendar_redirect_uri]
                    }
                },
                scopes=SCOPES
            )
            flow.redirect_uri = calendar_redirect_uri
            
            # Add state parameter to identify user
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='false',  # Don't include previously granted scopes
                prompt='consent',  # Force consent screen to ensure fresh permissions
                state=user_id
            )
            
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error creating authorization URL: {e}")
            raise

    def exchange_code_for_credentials(self, code: str, user_id: str) -> Dict[str, Any]:
        """Exchange authorization code for credentials"""
        try:
            # Use calendar-specific redirect URI if available, otherwise fall back to general one
            calendar_redirect_uri = settings.google_calendar_redirect_uri or settings.google_redirect_uri
            
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [calendar_redirect_uri]
                    }
                },
                scopes=SCOPES
            )
            flow.redirect_uri = calendar_redirect_uri
            
            # Exchange code for credentials
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Store credentials for the user
            credentials_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            return credentials_data
            
        except Exception as e:
            logger.error(f"Error exchanging code for credentials: {e}")
            raise

    def build_service(self, credentials_data: Dict[str, Any]):
        """Build Google Calendar service with stored credentials"""
        try:
            # Debug: Log what we received
            logger.info(f"Received credentials data keys: {list(credentials_data.keys())}")
            
            # Ensure all required fields are present
            required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
            missing_fields = [field for field in required_fields if field not in credentials_data]
            
            if missing_fields:
                logger.error(f"Missing required credential fields: {missing_fields}")
                raise ValueError(f"Missing required credential fields: {missing_fields}")
            
            # Create credentials object
            credentials = Credentials.from_authorized_user_info(credentials_data, SCOPES)
            
            # Refresh token if needed
            if not credentials.valid:
                if credentials.expired and credentials.refresh_token:
                    logger.info("Refreshing expired credentials")
                    credentials.refresh(Request())
            
            self.service = build('calendar', 'v3', credentials=credentials)
            self.credentials = credentials
            
        except Exception as e:
            logger.error(f"Error building calendar service: {e}")
            raise

    async def sync_calendar_events(self, user_id: str, credentials_data: Dict[str, Any], 
                                 start_date: Optional[datetime] = None, 
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Sync calendar events from Google Calendar"""
        try:
            self.build_service(credentials_data)
            
            # Default to next 30 days if no dates provided
            if not start_date:
                start_date = datetime.utcnow()
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            # Get events from Google Calendar
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Process and store events (you might want to store these in your database)
            synced_events = []
            for event in events:
                event_data = {
                    'google_event_id': event.get('id'),
                    'title': event.get('summary', 'No Title'),
                    'description': event.get('description', ''),
                    'start_time': event['start'].get('dateTime', event['start'].get('date')),
                    'end_time': event['end'].get('dateTime', event['end'].get('date')),
                    'attendees': [attendee.get('email') for attendee in event.get('attendees', [])],
                    'location': event.get('location', ''),
                    'status': event.get('status', 'confirmed'),
                    'user_id': user_id
                }
                synced_events.append(event_data)
            
            return {
                'success': True,
                'events_synced': len(synced_events),
                'events': synced_events,
                'last_sync': datetime.utcnow()
            }
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            raise Exception(f"Calendar sync failed: {e}")
        except Exception as e:
            logger.error(f"Error syncing calendar: {e}")
            raise

    async def create_calendar_event(self, credentials_data: Dict[str, Any], 
                                  event_data: CalendarEventCreate) -> CalendarEventResponse:
        """Create a new calendar event"""
        try:
            self.build_service(credentials_data)
            
            # Prepare event for Google Calendar
            event = {
                'summary': event_data.title,
                'description': event_data.description,
                'start': {
                    'dateTime': event_data.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': event_data.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'attendees': [{'email': email} for email in event_data.attendee_emails],
                'location': event_data.location,
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"mentto-{datetime.utcnow().timestamp()}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                } if event_data.meeting_link else None
            }
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1 if event_data.meeting_link else 0
            ).execute()
            
            # Extract meeting link if created
            meeting_link = None
            if created_event.get('conferenceData'):
                meeting_link = created_event['conferenceData'].get('entryPoints', [{}])[0].get('uri')
            
            return CalendarEventResponse(
                event_id=created_event['id'],
                title=created_event['summary'],
                description=created_event.get('description', ''),
                start_time=datetime.fromisoformat(created_event['start']['dateTime'].replace('Z', '+00:00')),
                end_time=datetime.fromisoformat(created_event['end']['dateTime'].replace('Z', '+00:00')),
                attendee_emails=[attendee.get('email') for attendee in created_event.get('attendees', [])],
                location=created_event.get('location', ''),
                meeting_link=meeting_link,
                status=created_event.get('status', 'confirmed'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
        except HttpError as e:
            logger.error(f"Google Calendar API error creating event: {e}")
            raise Exception(f"Failed to create calendar event: {e}")
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            raise

    async def get_availability_slots(self, credentials_data: Dict[str, Any], 
                                   start_date: datetime, end_date: datetime,
                                   slot_duration_minutes: int = 30) -> List[AvailabilitySlot]:
        """Get availability slots for a date range"""
        try:
            self.build_service(credentials_data)
            
            # Get busy times from Google Calendar
            freebusy_result = self.service.freebusy().query(
                body={
                    'timeMin': start_date.isoformat() + 'Z',
                    'timeMax': end_date.isoformat() + 'Z',
                    'items': [{'id': 'primary'}]
                }
            ).execute()
            
            busy_times = freebusy_result['calendars']['primary'].get('busy', [])
            
            # Generate time slots
            slots = []
            current_time = start_date
            
            while current_time < end_date:
                slot_end = current_time + timedelta(minutes=slot_duration_minutes)
                
                # Check if this slot conflicts with busy times
                is_available = True
                conflicting_event = None
                
                for busy_period in busy_times:
                    busy_start = datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00'))
                    busy_end = datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                    
                    # Check for overlap
                    if (current_time < busy_end and slot_end > busy_start):
                        is_available = False
                        conflicting_event = busy_period.get('summary', 'Busy')
                        break
                
                slots.append(AvailabilitySlot(
                    start_time=current_time,
                    end_time=slot_end,
                    is_available=is_available,
                    event_title=conflicting_event if not is_available else None
                ))
                
                current_time = slot_end
            
            return slots
            
        except HttpError as e:
            logger.error(f"Google Calendar API error getting availability: {e}")
            raise Exception(f"Failed to get availability: {e}")
        except Exception as e:
            logger.error(f"Error getting availability slots: {e}")
            raise

    async def send_meeting_invitation(self, credentials_data: Dict[str, Any], 
                                    invitation_data: SendInvitationRequest) -> CalendarEventResponse:
        """Send a meeting invitation to a mentee"""
        try:
            # Create calendar event with the mentee as attendee
            event_data = CalendarEventCreate(
                title=invitation_data.event_title,
                description=invitation_data.event_description,
                start_time=invitation_data.start_time,
                end_time=invitation_data.end_time,
                attendee_emails=[invitation_data.mentee_email],
                meeting_link=invitation_data.meeting_link
            )
            
            # Create the event (this will send invitation to mentee)
            return await self.create_calendar_event(credentials_data, event_data)
            
        except Exception as e:
            logger.error(f"Error sending meeting invitation: {e}")
            raise


# Service instance
calendar_service = GoogleCalendarService()
