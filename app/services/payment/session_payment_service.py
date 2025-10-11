import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
import razorpay

from app.core.database import get_supabase
from app.core.config import settings
from app.models.models import (
    SessionCreateRequest, SessionResponse, SessionPaymentRequest, 
    SessionPaymentResponse, TransferRequest, TransferResponse
)

logger = logging.getLogger(__name__)

class SessionPaymentService:
    def __init__(self):
        self.supabase = get_supabase()
        
        # Initialize Razorpay client
        if not settings.razor_pay_key_id or not settings.razor_pay_key_seceret:
            # Do not crash app at startup
            logger.warning("Razorpay credentials not configured; session payment service disabled")
            self.enabled = False
            self.client = None
        else:
            self.enabled = True
            self.client = razorpay.Client(
                auth=(settings.razor_pay_key_id, settings.razor_pay_key_seceret)
            )

    async def create_session(
        self, 
        mentee_id: str, 
        session_data: SessionCreateRequest
    ) -> SessionResponse:
        """Create a new session"""
        try:
            logger.info(f"Creating session for mentee: {mentee_id}")

            # Verify mentor has bank details and Razorpay account setup
            bank_result = self.supabase.table("bank_details").select("*").eq("user_id", session_data.mentor_id).execute()
            if not bank_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mentor bank details not found"
                )

            bank_details = bank_result.data[0]
            if not bank_details.get("razorpay_account_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mentor Razorpay account not setup"
                )

            # Derive legacy schema fields
            start_dt = session_data.scheduled_at
            from datetime import timedelta
            end_dt = start_dt + timedelta(minutes=session_data.duration_minutes)
            scheduled_date = start_dt.date().isoformat()
            start_time_str = start_dt.strftime("%H:%M")
            end_time_str = end_dt.strftime("%H:%M")

            # Create session record
            session_record = {
                "id": str(uuid.uuid4()),
                "mentee_id": mentee_id,
                "mentor_id": session_data.mentor_id,
                "title": session_data.title,
                "description": session_data.description,
                "scheduled_at": session_data.scheduled_at.isoformat(),
                "scheduled_date": scheduled_date,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "duration_minutes": session_data.duration_minutes,
                "amount": session_data.amount,
                "currency": "INR",
                "status": "scheduled",
                "call_type": "video_call",
                "timezone": "UTC",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("sessions").insert(session_record).execute()

            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create session"
                )

            return SessionResponse.model_validate(result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create session: {str(e)}"
            )

    async def create_payment_order(
        self, 
        mentee_id: str, 
        payment_data: SessionPaymentRequest
    ) -> SessionPaymentResponse:
        """Create Razorpay order for session payment"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            logger.info(f"Creating payment order for session: {payment_data.session_id}")

            # Get session details
            session_result = self.supabase.table("sessions").select("*").eq("id", payment_data.session_id).execute()
            if not session_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )

            session = session_result.data[0]

            # Verify mentee owns this session
            if session["mentee_id"] != mentee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only pay for your own sessions"
                )

            # Check if payment already exists
            existing_payment = self.supabase.table("session_payments").select("*").eq(
                "session_id", payment_data.session_id
            ).execute()

            if existing_payment.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment already exists for this session"
                )

            # Create Razorpay order
            amount_in_paise = int(session["amount"] * 100)  # Convert to paise
            
            # Generate short receipt (<= 40 chars)
            short_id = payment_data.session_id.replace("-", "")[:10]
            short_ts = int(datetime.now().timestamp())
            receipt_value = f"sess_{short_id}_{short_ts}"

            order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": receipt_value,
                "notes": {
                    "session_id": payment_data.session_id,
                    "mentee_id": mentee_id,
                    "mentor_id": session["mentor_id"],
                    "type": "session_payment"
                }
            }

            razorpay_order = self.client.order.create(data=order_data)

            # Create payment record
            payment_record = {
                "id": str(uuid.uuid4()),
                "session_id": payment_data.session_id,
                "mentee_id": mentee_id,
                "mentor_id": session["mentor_id"],
                "razorpay_order_id": razorpay_order["id"],
                "amount": session["amount"],
                "currency": "INR",
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("session_payments").insert(payment_record).execute()

            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create payment record"
                )

            return SessionPaymentResponse(
                session_id=payment_data.session_id,
                razorpay_order_id=razorpay_order["id"],
                amount=session["amount"],
                currency="INR",
                key_id=settings.razor_pay_key_id
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating payment order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create payment order: {str(e)}"
            )

    async def handle_payment_success(
        self, 
        razorpay_payment_id: str, 
        razorpay_order_id: str
    ):
        """Handle successful payment from webhook"""
        try:
            logger.info(f"Handling payment success: {razorpay_payment_id}")

            # Get payment record
            payment_result = self.supabase.table("session_payments").select("*").eq(
                "razorpay_order_id", razorpay_order_id
            ).execute()

            if not payment_result.data:
                logger.error(f"Payment record not found for order: {razorpay_order_id}")
                return

            payment = payment_result.data[0]

            # Update payment status
            update_data = {
                "razorpay_payment_id": razorpay_payment_id,
                "status": "captured",
                "captured_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            self.supabase.table("session_payments").update(update_data).eq(
                "id", payment["id"]
            ).execute()

            # Update session status to confirmed
            await self._update_session_status(payment["session_id"], "confirmed")

            # Generate meeting link and send calendar invites
            await self._send_session_calendar_invites(payment["session_id"])

            # Schedule transfer for 7 days later
            await self._schedule_transfer(payment["id"], payment["mentor_id"], payment["amount"])

            logger.info(f"Payment {razorpay_payment_id} processed successfully")

        except Exception as e:
            logger.error(f"Error handling payment success: {e}")

    async def _schedule_transfer(self, payment_id: str, mentor_id: str, amount: float):
        """Schedule transfer to mentor (70% after 7 days)"""
        try:
            # Calculate 70% of the amount
            transfer_amount = amount * 0.7
            scheduled_at = datetime.utcnow() + timedelta(days=7)

            transfer_record = {
                "id": str(uuid.uuid4()),
                "session_payment_id": payment_id,
                "mentor_id": mentor_id,
                "amount": transfer_amount,
                "currency": "INR",
                "status": "pending",
                "scheduled_at": scheduled_at.isoformat(),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("transfers").insert(transfer_record).execute()

            if result.data:
                logger.info(f"Scheduled transfer of {transfer_amount} for mentor {mentor_id} on {scheduled_at}")

        except Exception as e:
            logger.error(f"Error scheduling transfer: {e}")

    async def _update_session_status(self, session_id: str, status: str):
        """Update session status after payment confirmation"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.supabase.table("sessions").update(update_data).eq("id", session_id).execute()
            logger.info(f"Updated session {session_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Error updating session status: {e}")

    async def _send_session_calendar_invites(self, session_id: str):
        """Send calendar invites for confirmed session"""
        try:
            # Get session details
            session_result = self.supabase.table("sessions").select("*").eq("id", session_id).execute()
            if not session_result.data:
                logger.error(f"Session {session_id} not found")
                return

            session = session_result.data[0]

            # Get mentor and mentee details
            mentor_result = self.supabase.table("users").select("email, full_name").eq("user_id", session["mentor_id"]).execute()
            mentee_result = self.supabase.table("users").select("email, full_name").eq("user_id", session["mentee_id"]).execute()

            if not mentor_result.data or not mentee_result.data:
                logger.error(f"User details not found for session {session_id}")
                return

            mentor_email = mentor_result.data[0]["email"]
            mentee_email = mentee_result.data[0]["email"]
            mentor_name = mentor_result.data[0]["full_name"]
            mentee_name = mentee_result.data[0]["full_name"]

            # Generate Google Meet link
            meeting_link = await self._generate_meeting_link(session_id)

            # Update session with meeting link
            self.supabase.table("sessions").update({
                "meeting_link": meeting_link,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", session_id).execute()

            # Send calendar invites
            await self._create_calendar_event(
                session=session,
                mentor_email=mentor_email,
                mentee_email=mentee_email,
                mentor_name=mentor_name,
                mentee_name=mentee_name,
                meeting_link=meeting_link
            )

            logger.info(f"Sent calendar invites for session {session_id}")

        except Exception as e:
            logger.error(f"Error sending session calendar invites: {e}")

    async def _generate_meeting_link(self, session_id: str) -> str:
        """Generate a Google Meet link for the session"""
        try:
            # For now, generate a simple Google Meet link
            # In production, you might want to use Google Calendar API to create actual meeting
            base_url = "https://meet.google.com"
            # Generate a unique meeting code (in production, use proper Google Meet API)
            meeting_code = f"mentto-{session_id[:8]}"
            return f"{base_url}/{meeting_code}"
        except Exception as e:
            logger.error(f"Error generating meeting link: {e}")
            return "https://meet.google.com/mentto-session"

    async def _create_calendar_event(self, session: dict, mentor_email: str, mentee_email: str, 
                                   mentor_name: str, mentee_name: str, meeting_link: str):
        """Create calendar event and send invites"""
        try:
            from app.services.calendar.schedule_call_service import schedule_call_service
            
            # Create a ScheduleCallRequest object for calendar integration
            from app.models.models import ScheduleCallRequest
            from datetime import datetime
            
            # Parse session scheduled time
            scheduled_at = datetime.fromisoformat(session["scheduled_at"].replace('Z', '+00:00'))
            duration_minutes = session.get("duration_minutes", 60)
            end_time = scheduled_at + timedelta(minutes=duration_minutes)
            
            request = ScheduleCallRequest(
                mentor_email=mentor_email,
                start_time=scheduled_at,
                end_time=end_time,
                title=session.get("title", "Mentorship Session"),
                description=session.get("description", "Mentorship session with payment confirmed"),
                meeting_link=meeting_link,
                notes=f"Session ID: {session['id']}"
            )
            
            # Send calendar invites using existing service
            await schedule_call_service._send_calendar_invites(
                mentee_email,
                mentor_email,
                request,
                session["id"]
            )
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")

    async def process_transfer(self, transfer_data: TransferRequest) -> TransferResponse:
        """Process transfer to mentor"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            logger.info(f"Processing transfer for payment: {transfer_data.payment_id}")

            # Get transfer record
            transfer_result = self.supabase.table("transfers").select("*").eq(
                "session_payment_id", transfer_data.payment_id
            ).execute()

            if not transfer_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Transfer not found"
                )

            transfer = transfer_result.data[0]

            if transfer["status"] != "pending":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Transfer already {transfer['status']}"
                )

            # Get mentor's Razorpay account ID from bank_details
            bank_result = self.supabase.table("bank_details").select("razorpay_account_id, razorpay_route_account_id").eq(
                "user_id", transfer["mentor_id"]
            ).execute()
            
            if not bank_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mentor bank details not found"
                )
            
            bank_details = bank_result.data[0]
            # Prefer razorpay_route_account_id if present, else use razorpay_account_id
            razorpay_account_id = bank_details.get("razorpay_route_account_id") or bank_details.get("razorpay_account_id")
            
            if not razorpay_account_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mentor has no Razorpay account configured"
                )

            # Get payment details
            payment_result = self.supabase.table("session_payments").select("*").eq(
                "id", transfer_data.payment_id
            ).execute()

            if not payment_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            payment = payment_result.data[0]

            # Create Razorpay transfer
            amount_in_paise = int(transfer["amount"] * 100)
            
            transfer_payload = {
                "transfers": [
                    {
                        "account": razorpay_account_id,
                        "amount": amount_in_paise,
                        "currency": "INR"
                    }
                ]
            }

            razorpay_transfer = self.client.payment.transfer(
                payment["razorpay_payment_id"],
                transfer_payload
            )

            # Update transfer record
            update_data = {
                "razorpay_transfer_id": razorpay_transfer["id"],
                "status": "processed",
                "processed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("transfers").update(update_data).eq(
                "id", transfer["id"]
            ).execute()

            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update transfer record"
                )

            return TransferResponse.model_validate(result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing transfer: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process transfer: {str(e)}"
            )


# Create service instance
session_payment_service = SessionPaymentService()
