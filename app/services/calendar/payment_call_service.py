"""
Payment-First Call Scheduling Service
Creates calls with pending payment status and handles payment verification
"""
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.database import get_supabase
from app.models.models import PendingCallRequest, PaymentVerificationRequest, ScheduledCall
from app.services.payment.payment_service import payment_service

logger = logging.getLogger(__name__)

class PaymentCallService:
    def __init__(self):
        self.supabase = get_supabase()

    async def create_pending_call(
        self, 
        mentee_id: str,
        mentee_email: str,
        request: PendingCallRequest
    ) -> Dict[str, Any]:
        """Create a call with pending payment status"""
        try:
            logger.info(f"Creating pending call between {mentee_email} and {request.mentor_email}")
            
            # Validate mentor exists
            mentor_info = await self._get_mentor_info(request.mentor_email)
            if not mentor_info:
                raise Exception(f"Mentor not found: {request.mentor_email}")
            
            # Check if the time slot is still available
            is_available = await self._check_slot_availability(
                request.mentor_email, request.start_time, request.end_time
            )
            if not is_available:
                raise Exception("Time slot is no longer available")
            
            # Create Razorpay order for the call
            payment_order = await self._create_payment_order(
                mentee_id, request.amount, request.currency, request.mentor_email
            )
            
            # Create scheduled call record with pending payment
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
                "status": "pending_payment",
                "notes": request.notes,
                "payment_amount": request.amount,
                "payment_currency": request.currency,
                "payment_status": "pending",
                "razorpay_order_id": payment_order["razorpay_order_id"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert into database
            result = self.supabase.table("scheduled_calls").insert(call_record).execute()
            
            if not result.data:
                raise Exception("Failed to create pending call record")
            
            return {
                "call_id": call_id,
                "payment_order": payment_order,
                "status": "pending_payment",
                "message": "Call created. Please complete payment to confirm."
            }
            
        except Exception as e:
            logger.error(f"Error creating pending call: {e}")
            raise

    async def verify_payment_and_confirm_call(
        self, 
        request: PaymentVerificationRequest
    ) -> ScheduledCall:
        """Verify payment and confirm the call"""
        try:
            logger.info(f"Verifying payment for call {request.call_id}")
            
            # Get the call record
            call_result = self.supabase.table("scheduled_calls").select("*").eq("id", request.call_id).execute()
            
            if not call_result.data:
                raise Exception("Call not found")
            
            call_data = call_result.data[0]
            
            # Verify payment with Razorpay
            payment_verified = await self._verify_razorpay_payment(
                request.razorpay_order_id,
                request.razorpay_payment_id,
                request.razorpay_signature
            )
            
            if not payment_verified:
                # Update payment status to failed
                await self._update_payment_status(request.call_id, "failed")
                raise Exception("Payment verification failed")
            
            # Update call with payment details and mark completed if required by product
            update_data = {
                "payment_id": request.razorpay_payment_id,
                "payment_status": "success",
                "status": "confirmed",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("scheduled_calls").update(update_data).eq("id", request.call_id).execute()
            
            if not result.data:
                raise Exception("Failed to update call with payment details")
            
            # Trigger Google Meet invites immediately after confirming payment
            await self._send_calendar_invites(request.call_id)
            
            # Return the updated call
            return await self._get_scheduled_call(request.call_id)
            
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
            raise

    async def _get_mentor_info(self, mentor_email: str) -> Optional[Dict[str, Any]]:
        """Get mentor information from database"""
        try:
            result = self.supabase.table("users").select(
                "user_id, email"
            ).eq("email", mentor_email).execute()
            
            if not result.data:
                return None
            
            user = result.data[0]
            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user["email"].split("@")[0],
                "role": "mentor"
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
            from googleapiclient.discovery import build
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
                    from datetime import datetime
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

    async def _create_payment_order(
        self, 
        mentee_id: str, 
        amount: float, 
        currency: str,
        mentor_email: str
    ) -> Dict[str, Any]:
        """Create a Razorpay order for the call"""
        try:
            from app.models.models import PaymentCreate
            
            payment_data = PaymentCreate(
                amount=amount,
                currency=currency,
                mentor_id="",  # We'll use mentor_email instead
                session_id="",  # Not needed for call scheduling
                description=f"Mentorship call with {mentor_email}",
                notes=f"Call payment for {mentee_id}"
            )
            
            # Create order with Razorpay
            order_data = await payment_service.create_payment_order(payment_data, mentee_id)
            
            return {
                "razorpay_order_id": order_data["razorpay_order_id"],
                "amount": amount,
                "currency": currency,
                "key_id": order_data["key_id"]
            }
            
        except Exception as e:
            logger.error(f"Error creating payment order: {e}")
            raise

    async def _verify_razorpay_payment(
        self, 
        order_id: str, 
        payment_id: str, 
        signature: str
    ) -> bool:
        """Verify Razorpay payment signature"""
        try:
            return payment_service._verify_payment_signature(order_id, payment_id, signature)
        except Exception as e:
            logger.error(f"Error verifying payment signature: {e}")
            return False

    async def _update_payment_status(self, call_id: str, status: str):
        """Update payment status in database"""
        try:
            update_data = {
                "payment_status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("scheduled_calls").update(update_data).eq("id", call_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")

    async def _send_calendar_invites(self, call_id: str):
        """Send calendar invites for the confirmed call"""
        try:
            # This will be handled by the Supabase function
            # For now, we'll just log that invites should be sent
            logger.info(f"Calendar invites should be sent for call {call_id}")
            
        except Exception as e:
            logger.error(f"Error sending calendar invites: {e}")

    async def _get_scheduled_call(self, call_id: str) -> ScheduledCall:
        """Get scheduled call by ID"""
        try:
            result = self.supabase.table("scheduled_calls").select("*").eq("id", call_id).execute()
            
            if not result.data:
                raise Exception("Call not found")
            
            call_data = result.data[0]
            return self._format_scheduled_call(call_data)
            
        except Exception as e:
            logger.error(f"Error getting scheduled call: {e}")
            raise

    async def _get_user_calendar_credentials(self, email: str):
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
            from google.oauth2.credentials import Credentials
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
            payment_id=call_data.get("payment_id"),
            payment_amount=call_data.get("payment_amount"),
            payment_currency=call_data.get("payment_currency"),
            payment_status=call_data.get("payment_status"),
            razorpay_order_id=call_data.get("razorpay_order_id"),
            created_at=datetime.fromisoformat(call_data["created_at"]),
            updated_at=datetime.fromisoformat(call_data["updated_at"])
        )


# Create service instance
payment_call_service = PaymentCallService()
