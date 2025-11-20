"""
Session Service for managing mentorship sessions
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, time

from app.core.database import get_supabase
from app.models.models import (
    SessionCreate, SessionUpdate, SessionResponse, SessionSummary,
    CallType, SessionStatus
)

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self):
        self.supabase = get_supabase()

    async def create_session(self, user_id: str, session_data: SessionCreate, user_role: str = "mentee") -> Optional[SessionResponse]:
        """Create a new mentorship session"""
        try:
            # Determine mentee_id and mentor_id based on user role
            if user_role == "mentee":
                mentee_id = user_id
                mentor_id = session_data.other_user_id
            elif user_role == "mentor":
                mentee_id = session_data.other_user_id  # The mentor is scheduling with a mentee
                mentor_id = user_id
            else:
                raise ValueError("Invalid user role. Must be 'mentee' or 'mentor'")
            
            logger.info(f"Creating session for {user_role} {user_id}: mentee_id={mentee_id}, mentor_id={mentor_id}")
            
            # Verify mentorship relationship exists if mentorship_interest_id is provided
            if session_data.mentorship_interest_id:
                logger.info(f"Checking mentorship relationship: {session_data.mentorship_interest_id}")
                mentorship_check = self.supabase.table("mentorship_interest").select("id, status").eq("id", session_data.mentorship_interest_id).eq("mentee_id", mentee_id).eq("mentor_id", mentor_id).execute()
                if not mentorship_check.data:
                    raise ValueError("Invalid mentorship interest ID or no relationship found")
            
            # Prepare session data for database
            session_dict = {
                "mentee_id": mentee_id,
                "mentor_id": mentor_id,
                "mentorship_interest_id": session_data.mentorship_interest_id,
                "call_type": session_data.call_type.value,
                "scheduled_date": session_data.scheduled_date,
                "start_time": session_data.start_time,
                "end_time": session_data.end_time,
                "timezone": session_data.timezone,
                "notes": session_data.notes,
                "status": "scheduled"
            }
            
            logger.info(f"Session data prepared: {session_dict}")
            
            # Insert session
            result = self.supabase.table("sessions").insert(session_dict).execute()
            
            logger.info(f"Insert result: {result}")
            
            if result.data:
                session_id = result.data[0]["id"]
                logger.info(f"Session created with ID: {session_id}")
                return await self.get_session_by_id(session_id)
            else:
                logger.error(f"Failed to create session for mentee {mentee_id} and mentor {session_data.mentor_id}")
                logger.error(f"Insert result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_session_by_id(self, session_id: str) -> Optional[SessionResponse]:
        """Get a session by ID with user details, payment, and scheduled calls data"""
        try:
            logger.info(f"Getting session by ID: {session_id}")
            
            # First get the session data
            result = self.supabase.table("sessions").select("*").eq("id", session_id).execute()
            
            if not result.data:
                logger.error(f"Session not found: {session_id}")
                return None
            
            session_data = result.data[0]
            logger.info(f"Session data retrieved: {session_data}")
            
            # Get user details separately to avoid complex joins
            mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentee_id"]).execute()
            mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentor_id"]).execute()
            
            # Add user details to session data
            if mentee_result.data:
                session_data["mentee_name"] = mentee_result.data[0]["full_name"]
                session_data["mentee_email"] = mentee_result.data[0]["email"]
            
            if mentor_result.data:
                session_data["mentor_name"] = mentor_result.data[0]["full_name"]
                session_data["mentor_email"] = mentor_result.data[0]["email"]
            
            # Preserve payment_status from sessions table (primary source)
            # This is what we update when payment is verified
            # If not present, default to "pending"
            if "payment_status" not in session_data or session_data.get("payment_status") is None:
                session_data["payment_status"] = "pending"
            
            # Get payment data from session_payments table
            payment_result = self.supabase.table("session_payments").select("*").eq("session_id", session_id).execute()
            if payment_result.data:
                payment_data = payment_result.data[0]
                session_data["payment_id"] = payment_data.get("id")
                session_data["payment_amount"] = payment_data.get("amount")
                session_data["payment_currency"] = payment_data.get("currency")
                # Keep payment_status from sessions table - don't overwrite with session_payments status
                # The sessions.payment_status is the source of truth
                session_data["razorpay_order_id"] = payment_data.get("razorpay_order_id")
                session_data["razorpay_payment_id"] = payment_data.get("razorpay_payment_id")
            
            # Get scheduled calls data
            scheduled_call_result = self.supabase.table("scheduled_calls").select("*").eq("mentee_id", session_data["mentee_id"]).eq("mentor_id", session_data["mentor_id"]).execute()
            if scheduled_call_result.data:
                # Find the most relevant scheduled call (you might want to add more logic here)
                call_data = scheduled_call_result.data[0]
                session_data["scheduled_call_id"] = call_data.get("id")
                session_data["scheduled_call_status"] = call_data.get("status")
                session_data["scheduled_call_title"] = call_data.get("title")
                session_data["scheduled_call_description"] = call_data.get("description")
            
            return self._convert_to_session_response(session_data)
            
        except Exception as e:
            logger.error(f"Error getting session by ID {session_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_sessions_by_mentee(self, mentee_id: str, limit: int = 50, offset: int = 0) -> List[SessionResponse]:
        """Get all sessions for a specific mentee with payment and scheduled calls data"""
        try:
            logger.info(f"Getting sessions for mentee: {mentee_id}")
            
            # Get sessions without complex joins first
            result = self.supabase.table("sessions").select("*").eq("mentee_id", mentee_id).order("scheduled_date", desc=True).order("start_time", desc=True).range(offset, offset + limit - 1).execute()
            
            logger.info(f"Found {len(result.data)} sessions for mentee {mentee_id}")
            
            sessions = []
            for session_data in result.data:
                # Get user details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentor_id"]).execute()
                
                # Add user details to session data
                if mentee_result.data:
                    session_data["mentee_name"] = mentee_result.data[0]["full_name"]
                    session_data["mentee_email"] = mentee_result.data[0]["email"]
                
                if mentor_result.data:
                    session_data["mentor_name"] = mentor_result.data[0]["full_name"]
                    session_data["mentor_email"] = mentor_result.data[0]["email"]
                
                # Add scheduling information - since we're getting sessions by mentee, the mentee is the one who scheduled
                session_data["scheduled_by_user_id"] = session_data["mentee_id"]
                session_data["invited_by_user_id"] = session_data["mentor_id"]
                
                # Enrich with payment and scheduled calls data
                enriched_session_data = await self._enrich_session_with_payment_and_calls(session_data)
                
                session = self._convert_to_session_response(enriched_session_data)
                if session:
                    sessions.append(session)
            
            logger.info(f"Successfully converted {len(sessions)} sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions for mentee {mentee_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_sessions_by_mentor(self, mentor_id: str, limit: int = 50, offset: int = 0) -> List[SessionResponse]:
        """Get all sessions for a specific mentor with payment and scheduled calls data"""
        try:
            logger.info(f"Getting sessions for mentor: {mentor_id}")
            
            # Get sessions without complex joins first
            result = self.supabase.table("sessions").select("*").eq("mentor_id", mentor_id).order("scheduled_date", desc=True).order("start_time", desc=True).range(offset, offset + limit - 1).execute()
            
            logger.info(f"Found {len(result.data)} sessions for mentor {mentor_id}")
            
            sessions = []
            for session_data in result.data:
                # Get user details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentor_id"]).execute()
                
                # Add user details to session data
                if mentee_result.data:
                    session_data["mentee_name"] = mentee_result.data[0]["full_name"]
                    session_data["mentee_email"] = mentee_result.data[0]["email"]
                
                if mentor_result.data:
                    session_data["mentor_name"] = mentor_result.data[0]["full_name"]
                    session_data["mentor_email"] = mentor_result.data[0]["email"]
                
                # Add scheduling information - since we're getting sessions by mentor, we need to determine who actually scheduled
                # This is a simplified approach - in a real scenario, you'd want to store this in the database
                # For now, we'll assume if mentor is viewing, they were invited (mentee scheduled)
                session_data["scheduled_by_user_id"] = session_data["mentee_id"]
                session_data["invited_by_user_id"] = session_data["mentor_id"]
                
                # Enrich with payment and scheduled calls data
                enriched_session_data = await self._enrich_session_with_payment_and_calls(session_data)
                
                session = self._convert_to_session_response(enriched_session_data)
                if session:
                    sessions.append(session)
            
            logger.info(f"Successfully converted {len(sessions)} sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions for mentor {mentor_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_upcoming_sessions(self, user_id: str, user_role: str, limit: int = 10) -> List[SessionResponse]:
        """Get upcoming sessions for a user with payment and scheduled calls data"""
        try:
            today = datetime.now().date().isoformat()
            logger.info(f"Getting upcoming sessions for {user_role} {user_id} from {today}")
            
            if user_role == "mentee":
                result = self.supabase.table("sessions").select("*").eq("mentee_id", user_id).gte("scheduled_date", today).in_("status", ["scheduled", "confirmed"]).order("scheduled_date", desc=False).order("start_time", desc=False).limit(limit).execute()
            else:  # mentor
                result = self.supabase.table("sessions").select("*").eq("mentor_id", user_id).gte("scheduled_date", today).in_("status", ["scheduled", "confirmed"]).order("scheduled_date", desc=False).order("start_time", desc=False).limit(limit).execute()
            
            logger.info(f"Found {len(result.data)} upcoming sessions")
            
            sessions = []
            for session_data in result.data:
                # Get user details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", session_data["mentor_id"]).execute()
                
                # Add user details to session data
                if mentee_result.data:
                    session_data["mentee_name"] = mentee_result.data[0]["full_name"]
                    session_data["mentee_email"] = mentee_result.data[0]["email"]
                
                if mentor_result.data:
                    session_data["mentor_name"] = mentor_result.data[0]["full_name"]
                    session_data["mentor_email"] = mentor_result.data[0]["email"]
                
                # Enrich with payment and scheduled calls data
                enriched_session_data = await self._enrich_session_with_payment_and_calls(session_data)
                
                session = self._convert_to_session_response(enriched_session_data)
                if session:
                    sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting upcoming sessions for {user_role} {user_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def update_session(self, session_id: str, user_id: str, user_role: str, update_data: SessionUpdate) -> Optional[SessionResponse]:
        """Update an existing session"""
        try:
            # Verify the session belongs to the user
            existing_session = await self.get_session_by_id(session_id)
            if not existing_session:
                raise ValueError("Session not found")
            
            if user_role == "mentee" and existing_session.mentee_id != user_id:
                raise ValueError("You don't have permission to update this session")
            elif user_role == "mentor" and existing_session.mentor_id != user_id:
                raise ValueError("You don't have permission to update this session")
            
            # Prepare update data
            update_dict = {}
            if update_data.call_type is not None:
                update_dict["call_type"] = update_data.call_type.value
            if update_data.scheduled_date is not None:
                update_dict["scheduled_date"] = update_data.scheduled_date
            if update_data.start_time is not None:
                update_dict["start_time"] = update_data.start_time
            if update_data.end_time is not None:
                update_dict["end_time"] = update_data.end_time
            if update_data.timezone is not None:
                update_dict["timezone"] = update_data.timezone
            if update_data.notes is not None:
                update_dict["notes"] = update_data.notes
            if update_data.status is not None:
                update_dict["status"] = update_data.status.value
            if update_data.meeting_link is not None:
                update_dict["meeting_link"] = update_data.meeting_link
            if update_data.meeting_id is not None:
                update_dict["meeting_id"] = update_data.meeting_id
            
            if not update_dict:
                return existing_session
            
            # Update session
            result = self.supabase.table("sessions").update(update_dict).eq("id", session_id).execute()
            
            if result.data:
                return await self.get_session_by_id(session_id)
            return None
            
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            raise

    async def delete_session(self, session_id: str, user_id: str, user_role: str) -> bool:
        """Delete a session"""
        try:
            # Verify the session belongs to the user
            existing_session = await self.get_session_by_id(session_id)
            if not existing_session:
                raise ValueError("Session not found")
            
            if user_role == "mentee" and existing_session.mentee_id != user_id:
                raise ValueError("You don't have permission to delete this session")
            elif user_role == "mentor" and existing_session.mentor_id != user_id:
                raise ValueError("You don't have permission to delete this session")
            
            result = self.supabase.table("sessions").delete().eq("id", session_id).execute()
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            raise

    async def get_session_summary(self, user_id: str, user_role: str) -> Optional[SessionSummary]:
        """Get comprehensive session summary for a user"""
        try:
            # Get all sessions for the user
            if user_role == "mentee":
                sessions_result = self.supabase.table("sessions").select("*").eq("mentee_id", user_id).execute()
            else:  # mentor
                sessions_result = self.supabase.table("sessions").select("*").eq("mentor_id", user_id).execute()
            
            if not sessions_result.data:
                return SessionSummary(
                    total_sessions=0,
                    upcoming_sessions=0,
                    completed_sessions=0,
                    cancelled_sessions=0,
                    next_session=None,
                    recent_sessions=[]
                )
            
            sessions = sessions_result.data
            today = datetime.now().date().isoformat()
            
            # Calculate statistics
            total_sessions = len(sessions)
            upcoming_sessions = len([s for s in sessions if s["scheduled_date"] >= today and s["status"] in ["scheduled", "confirmed"]])
            completed_sessions = len([s for s in sessions if s["status"] == "completed"])
            cancelled_sessions = len([s for s in sessions if s["status"] == "cancelled"])
            
            # Get next session
            next_session = None
            upcoming = [s for s in sessions if s["scheduled_date"] >= today and s["status"] in ["scheduled", "confirmed"]]
            if upcoming:
                # Sort by date and time to get the next one
                upcoming.sort(key=lambda x: (x["scheduled_date"], x["start_time"]))
                next_session_data = upcoming[0]
                next_session = await self.get_session_by_id(next_session_data["id"])
            
            # Get recent sessions (last 5)
            recent_sessions = await self.get_sessions_by_mentee(user_id, limit=5) if user_role == "mentee" else await self.get_sessions_by_mentor(user_id, limit=5)
            
            return SessionSummary(
                total_sessions=total_sessions,
                upcoming_sessions=upcoming_sessions,
                completed_sessions=completed_sessions,
                cancelled_sessions=cancelled_sessions,
                next_session=next_session,
                recent_sessions=recent_sessions
            )
            
        except Exception as e:
            logger.error(f"Error getting session summary for {user_role} {user_id}: {e}")
            return None

    async def _enrich_session_with_payment_and_calls(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich session data with payment and scheduled calls information"""
        try:
            session_id = session_data["id"]
            
            # Preserve payment_status from sessions table (primary source)
            # This is what we update when payment is verified
            # If not present, default to "pending"
            if "payment_status" not in session_data or session_data.get("payment_status") is None:
                session_data["payment_status"] = "pending"
            
            # Get payment data from session_payments table
            payment_result = self.supabase.table("session_payments").select("*").eq("session_id", session_id).execute()
            if payment_result.data:
                payment_data = payment_result.data[0]
                session_data["payment_id"] = payment_data.get("id")
                session_data["payment_amount"] = payment_data.get("amount")
                session_data["payment_currency"] = payment_data.get("currency")
                # Keep payment_status from sessions table - don't overwrite with session_payments status
                # The sessions.payment_status is the source of truth
                session_data["razorpay_order_id"] = payment_data.get("razorpay_order_id")
                session_data["razorpay_payment_id"] = payment_data.get("razorpay_payment_id")
            
            # Get scheduled calls data
            scheduled_call_result = self.supabase.table("scheduled_calls").select("*").eq("mentee_id", session_data["mentee_id"]).eq("mentor_id", session_data["mentor_id"]).execute()
            if scheduled_call_result.data:
                # Find the most relevant scheduled call (you might want to add more logic here)
                call_data = scheduled_call_result.data[0]
                session_data["scheduled_call_id"] = call_data.get("id")
                session_data["scheduled_call_status"] = call_data.get("status")
                session_data["scheduled_call_title"] = call_data.get("title")
                session_data["scheduled_call_description"] = call_data.get("description")
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error enriching session data: {e}")
            return session_data

    def _convert_to_session_response(self, session_data: Dict[str, Any]) -> Optional[SessionResponse]:
        """Convert database record to SessionResponse"""
        try:
            logger.info(f"Converting session data: {session_data}")
            
            # Extract user details from session data
            mentee_name = session_data.get("mentee_name")
            mentee_email = session_data.get("mentee_email")
            mentor_name = session_data.get("mentor_name")
            mentor_email = session_data.get("mentor_email")
            
            # Handle datetime parsing more safely
            created_at = datetime.now()
            updated_at = datetime.now()
            
            if session_data.get("created_at"):
                try:
                    created_at_str = session_data["created_at"]
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                    created_at = datetime.fromisoformat(created_at_str)
                except Exception as e:
                    logger.warning(f"Failed to parse created_at '{session_data.get('created_at')}': {e}")
                    created_at = datetime.now()
            
            if session_data.get("updated_at"):
                try:
                    updated_at_str = session_data["updated_at"]
                    if updated_at_str.endswith('Z'):
                        updated_at_str = updated_at_str.replace('Z', '+00:00')
                    updated_at = datetime.fromisoformat(updated_at_str)
                except Exception as e:
                    logger.warning(f"Failed to parse updated_at '{session_data.get('updated_at')}': {e}")
                    updated_at = datetime.now()
            
                return SessionResponse(
                    id=session_data["id"],
                    mentee_id=session_data["mentee_id"],
                    mentor_id=session_data["mentor_id"],
                    mentorship_interest_id=session_data.get("mentorship_interest_id"),
                    call_type=session_data.get("call_type", "video_call"),
                    scheduled_date=session_data.get("scheduled_date", "2025-01-01"),
                    start_time=session_data.get("start_time", "00:00:00"),
                    end_time=session_data.get("end_time", "01:00:00"),
                    timezone=session_data.get("timezone", "UTC"),
                    notes=session_data.get("notes"),
                    status=session_data.get("status", "scheduled"),
                    meeting_link=session_data.get("meeting_link"),
                    meeting_id=session_data.get("meeting_id"),
                    created_at=created_at,
                    updated_at=updated_at,
                    mentee_name=mentee_name,
                    mentee_email=mentee_email,
                    mentor_name=mentor_name,
                    mentor_email=mentor_email,
                    # Payment information
                    payment_id=session_data.get("payment_id"),
                    payment_amount=session_data.get("payment_amount"),
                    payment_currency=session_data.get("payment_currency"),
                    payment_status=session_data.get("payment_status") or "pending",  # Default to pending if not set
                    razorpay_order_id=session_data.get("razorpay_order_id"),
                    razorpay_payment_id=session_data.get("razorpay_payment_id"),
                    # Scheduled calls information
                    scheduled_call_id=session_data.get("scheduled_call_id"),
                    scheduled_call_status=session_data.get("scheduled_call_status"),
                    scheduled_call_title=session_data.get("scheduled_call_title"),
                    scheduled_call_description=session_data.get("scheduled_call_description"),
                    # Session scheduling information
                    scheduled_by_user_id=session_data.get("scheduled_by_user_id"),
                    invited_by_user_id=session_data.get("invited_by_user_id")
                )
        except Exception as e:
            logger.error(f"Error converting session data to response: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

# Service instance
session_service = SessionService()
