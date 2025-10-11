import razorpay
import hashlib
import hmac
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.models import (
    PaymentCreate, PaymentResponse, PaymentUpdate, PaymentStatus, 
    PaymentMethod, RefundCreate, RefundResponse, PaymentSummary
)
from app.core.database import get_supabase


class PaymentService:
    def __init__(self):
        if not settings.razor_pay_key_id or not settings.razor_pay_key_seceret:
            # Do not crash app at startup
            self.enabled = False
            self.client = None
        else:
            self.enabled = True
            self.client = razorpay.Client(
                auth=(settings.razor_pay_key_id, settings.razor_pay_key_seceret)
            )
        self.supabase = get_supabase()

    async def create_payment_order(self, payment_data: PaymentCreate, mentee_id: str) -> Dict[str, Any]:
        """Create a Razorpay order for payment"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            # Get currency multiplier (smallest unit for each currency)
            currency_multiplier = self._get_currency_multiplier(payment_data.currency)
            amount_in_smallest_unit = int(payment_data.amount * currency_multiplier)
            
            order_data = {
                "amount": amount_in_smallest_unit,
                "currency": payment_data.currency.upper(),
                "receipt": f"mentto_payment_{mentee_id}_{int(datetime.now().timestamp())}",
                "notes": {
                    "mentee_id": mentee_id,
                    "mentor_id": payment_data.mentor_id,
                    "session_id": payment_data.session_id,
                    "description": payment_data.description
                }
            }
            
            # Create order with Razorpay
            razorpay_order = self.client.order.create(data=order_data)
            
            # Store payment record in database
            payment_record = {
                "mentee_id": mentee_id,
                "mentor_id": payment_data.mentor_id,
                "session_id": payment_data.session_id,
                "amount": payment_data.amount,
                "currency": payment_data.currency,
                "status": PaymentStatus.PENDING.value,
                "razorpay_order_id": razorpay_order["id"],
                "description": payment_data.description,
                "notes": payment_data.notes,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Insert into database
            result = self.supabase.table("payments").insert(payment_record).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create payment record"
                )
            
            payment_id = result.data[0]["id"]
            
            return {
                "payment_id": payment_id,
                "razorpay_order_id": razorpay_order["id"],
                "amount": payment_data.amount,
                "currency": payment_data.currency,
                "key_id": settings.razor_pay_key_id,
                "order_id": razorpay_order["id"]
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create payment order: {str(e)}"
            )

    async def verify_payment(self, payment_id: str, verification_data: Dict[str, str]) -> PaymentResponse:
        """Verify payment signature and update payment status"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            # Get payment record
            result = self.supabase.table("payments").select("*").eq("id", payment_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )
            
            payment_record = result.data[0]
            
            # Verify signature
            if not self._verify_payment_signature(
                payment_record["razorpay_order_id"],
                verification_data["razorpay_payment_id"],
                verification_data["razorpay_signature"]
            ):
                # Update payment status to failed
                await self._update_payment_status(
                    payment_id, 
                    PaymentStatus.FAILED.value,
                    verification_data["razorpay_payment_id"]
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid payment signature"
                )
            
            # Fetch payment details from Razorpay
            razorpay_payment = self.client.payment.fetch(verification_data["razorpay_payment_id"])
            
            # Update payment record
            update_data = {
                "status": PaymentStatus.SUCCESS.value,
                "razorpay_payment_id": verification_data["razorpay_payment_id"],
                "payment_method": razorpay_payment.get("method"),
                "razorpay_signature": verification_data["razorpay_signature"],
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("payments").update(update_data).eq("id", payment_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update payment status"
                )
            
            # Return updated payment response
            return await self._get_payment_response(payment_id)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify payment: {str(e)}"
            )

    async def get_payment_by_id(self, payment_id: str) -> PaymentResponse:
        """Get payment details by ID"""
        try:
            return await self._get_payment_response(payment_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get payment: {str(e)}"
            )

    async def get_user_payments(self, user_id: str, limit: int = 20, offset: int = 0) -> List[PaymentResponse]:
        """Get payments for a specific user"""
        try:
            result = self.supabase.table("payments").select(
                "*, mentee:mentee_id(*), mentor:mentor_id(*)"
            ).or_(f"mentee_id.eq.{user_id},mentor_id.eq.{user_id}").order(
                "created_at", desc=True
            ).range(offset, offset + limit - 1).execute()
            
            if not result.data:
                return []
            
            payments = []
            for payment in result.data:
                payments.append(self._format_payment_response(payment))
            
            return payments
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get user payments: {str(e)}"
            )

    async def create_refund(self, refund_data: RefundCreate) -> RefundResponse:
        """Create a refund for a payment"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            # Get payment record
            payment_result = self.supabase.table("payments").select("*").eq("id", refund_data.payment_id).execute()
            
            if not payment_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )
            
            payment_record = payment_result.data[0]
            
            if payment_record["status"] != PaymentStatus.SUCCESS.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only refund successful payments"
                )
            
            # Calculate refund amount
            refund_amount = refund_data.amount or payment_record["amount"]
            currency_multiplier = self._get_currency_multiplier(payment_record["currency"])
            refund_amount_smallest_unit = int(refund_amount * currency_multiplier)
            
            # Create refund with Razorpay
            razorpay_refund = self.client.payment.refund(
                payment_record["razorpay_payment_id"],
                {
                    "amount": refund_amount_smallest_unit,
                    "notes": {
                        "reason": refund_data.notes or "Refund requested"
                    }
                }
            )
            
            # Store refund record
            refund_record = {
                "payment_id": refund_data.payment_id,
                "razorpay_refund_id": razorpay_refund["id"],
                "amount": refund_amount,
                "status": razorpay_refund["status"],
                "notes": refund_data.notes,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("refunds").insert(refund_record).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create refund record"
                )
            
            # Update payment status if full refund
            if refund_amount >= payment_record["amount"]:
                await self._update_payment_status(
                    refund_data.payment_id,
                    PaymentStatus.REFUNDED.value
                )
            else:
                await self._update_payment_status(
                    refund_data.payment_id,
                    PaymentStatus.PARTIALLY_REFUNDED.value
                )
            
            return RefundResponse(
                id=result.data[0]["id"],
                payment_id=refund_data.payment_id,
                razorpay_refund_id=razorpay_refund["id"],
                amount=refund_amount,
                status=razorpay_refund["status"],
                notes=refund_data.notes,
                created_at=datetime.fromisoformat(result.data[0]["created_at"]),
                updated_at=datetime.fromisoformat(result.data[0]["updated_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create refund: {str(e)}"
            )

    async def get_payment_summary(self, user_id: str) -> PaymentSummary:
        """Get payment summary for a user"""
        try:
            # Get all payments for the user
            result = self.supabase.table("payments").select("*").or_(
                f"mentee_id.eq.{user_id},mentor_id.eq.{user_id}"
            ).execute()
            
            if not result.data:
                return PaymentSummary(
                    total_payments=0,
                    total_amount=0.0,
                    successful_payments=0,
                    failed_payments=0,
                    pending_payments=0,
                    total_refunds=0.0,
                    net_amount=0.0
                )
            
            payments = result.data
            total_payments = len(payments)
            total_amount = sum(p["amount"] for p in payments)
            successful_payments = len([p for p in payments if p["status"] == PaymentStatus.SUCCESS.value])
            failed_payments = len([p for p in payments if p["status"] == PaymentStatus.FAILED.value])
            pending_payments = len([p for p in payments if p["status"] == PaymentStatus.PENDING.value])
            
            # Get refunds
            refund_result = self.supabase.table("refunds").select("amount").in_(
                "payment_id", [p["id"] for p in payments]
            ).execute()
            
            total_refunds = sum(r["amount"] for r in refund_result.data) if refund_result.data else 0.0
            net_amount = total_amount - total_refunds
            
            return PaymentSummary(
                total_payments=total_payments,
                total_amount=total_amount,
                successful_payments=successful_payments,
                failed_payments=failed_payments,
                pending_payments=pending_payments,
                total_refunds=total_refunds,
                net_amount=net_amount
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get payment summary: {str(e)}"
            )

    def _verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify Razorpay payment signature"""
        try:
            message = f"{order_id}|{payment_id}"
            expected_signature = hmac.new(
                settings.razor_pay_key_seceret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False

    async def _update_payment_status(self, payment_id: str, status: str, razorpay_payment_id: str = None):
        """Update payment status in database"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if razorpay_payment_id:
            update_data["razorpay_payment_id"] = razorpay_payment_id
        
        self.supabase.table("payments").update(update_data).eq("id", payment_id).execute()

    async def _get_payment_response(self, payment_id: str) -> PaymentResponse:
        """Get formatted payment response"""
        result = self.supabase.table("payments").select(
            "*, mentee:mentee_id(*), mentor:mentor_id(*)"
        ).eq("id", payment_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        return self._format_payment_response(result.data[0])

    def _format_payment_response(self, payment_data: Dict[str, Any]) -> PaymentResponse:
        """Format payment data into PaymentResponse"""
        mentee_data = payment_data.get("mentee", {})
        mentor_data = payment_data.get("mentor", {})
        
        return PaymentResponse(
            id=payment_data["id"],
            razorpay_payment_id=payment_data.get("razorpay_payment_id"),
            razorpay_order_id=payment_data.get("razorpay_order_id"),
            amount=payment_data["amount"],
            currency=payment_data["currency"],
            status=PaymentStatus(payment_data["status"]),
            payment_method=PaymentMethod(payment_data["payment_method"]) if payment_data.get("payment_method") else None,
            mentee_id=payment_data["mentee_id"],
            mentor_id=payment_data["mentor_id"],
            session_id=payment_data.get("session_id"),
            description=payment_data.get("description"),
            notes=payment_data.get("notes"),
            razorpay_signature=payment_data.get("razorpay_signature"),
            created_at=datetime.fromisoformat(payment_data["created_at"]),
            updated_at=datetime.fromisoformat(payment_data["updated_at"]),
            mentee_name=f"{mentee_data.get('first_name', '')} {mentee_data.get('last_name', '')}".strip() if mentee_data else None,
            mentee_email=mentee_data.get("email") if mentee_data else None,
            mentor_name=f"{mentor_data.get('first_name', '')} {mentor_data.get('last_name', '')}".strip() if mentor_data else None,
            mentor_email=mentor_data.get("email") if mentor_data else None
        )

    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Handle Razorpay webhook events"""
        try:
            # If body already verified at route, allow pass-through
            if not webhook_data.get("__preverified"):
                if not self._verify_webhook_signature(webhook_data):
                    return False
            
            event = webhook_data.get("event")
            payload = webhook_data.get("payload", {}).get("payment", {})
            
            if event == "payment.captured":
                # Payment successful
                razorpay_payment_id = payload.get("id")
                razorpay_order_id = payload.get("order_id")
                
                # Handle regular payments
                await self._handle_payment_success(razorpay_payment_id, razorpay_order_id)
                
                # Handle call scheduling payments
                await self._handle_call_payment_success(razorpay_payment_id, razorpay_order_id)
                
                # Handle session payments
                await self._handle_session_payment_success(razorpay_payment_id, razorpay_order_id)
            
            elif event == "payment.failed":
                # Payment failed
                razorpay_order_id = payload.get("order_id")
                
                # Handle regular payments
                await self._handle_payment_failure(razorpay_order_id)
                
                # Handle call scheduling payments
                await self._handle_call_payment_failure(razorpay_order_id)
            
            return True
            
        except Exception as e:
            print(f"Webhook handling error: {str(e)}")
            return False

    async def _handle_payment_success(self, razorpay_payment_id: str, razorpay_order_id: str):
        """Handle successful payment for regular payments"""
        try:
            # Find payment by razorpay_order_id
            result = self.supabase.table("payments").select("*").eq(
                "razorpay_order_id", razorpay_order_id
            ).execute()
            
            if result.data:
                payment_id = result.data[0]["id"]
                await self._update_payment_status(
                    payment_id,
                    PaymentStatus.SUCCESS.value,
                    razorpay_payment_id
                )
        except Exception as e:
            logger.error(f"Error handling payment success: {e}")

    async def _handle_payment_failure(self, razorpay_order_id: str):
        """Handle failed payment for regular payments"""
        try:
            result = self.supabase.table("payments").select("*").eq(
                "razorpay_order_id", razorpay_order_id
            ).execute()
            
            if result.data:
                payment_id = result.data[0]["id"]
                await self._update_payment_status(
                    payment_id,
                    PaymentStatus.FAILED.value
                )
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")

    async def _handle_call_payment_success(self, razorpay_payment_id: str, razorpay_order_id: str):
        """Handle successful payment for call scheduling"""
        try:
            # Find scheduled call by razorpay_order_id
            result = self.supabase.table("scheduled_calls").select("*").eq(
                "razorpay_order_id", razorpay_order_id
            ).execute()
            
            if result.data:
                call_data = result.data[0]
                call_id = call_data["id"]
                
                # Update call with payment details
                update_data = {
                    "payment_id": razorpay_payment_id,
                    "payment_status": "success",
                    "status": "confirmed",
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                self.supabase.table("scheduled_calls").update(update_data).eq("id", call_id).execute()
                
                # Send calendar invites
                await self._send_calendar_invites_for_call(call_data)
                
                logger.info(f"Call {call_id} confirmed after successful payment")
                
        except Exception as e:
            logger.error(f"Error handling call payment success: {e}")

    async def _handle_session_payment_success(self, razorpay_payment_id: str, razorpay_order_id: str):
        """Handle successful payment for session payments"""
        try:
            from app.services.payment.session_payment_service import session_payment_service
            await session_payment_service.handle_payment_success(razorpay_payment_id, razorpay_order_id)
            
            # Also update scheduled_calls if payment_id matches
            await self._update_scheduled_calls_by_payment_id(razorpay_payment_id)
            
        except Exception as e:
            logger.error(f"Error handling session payment success: {e}")

    async def _update_scheduled_calls_by_payment_id(self, razorpay_payment_id: str):
        """Update scheduled calls by payment ID"""
        try:
            # Find scheduled calls with matching payment_id
            result = self.supabase.table("scheduled_calls").select("*").eq(
                "payment_id", razorpay_payment_id
            ).execute()
            
            if result.data:
                for call_data in result.data:
                    call_id = call_data["id"]
                    
                    # Update call with payment details
                    update_data = {
                        "payment_status": "completed",
                        "status": "confirmed",
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    self.supabase.table("scheduled_calls").update(update_data).eq("id", call_id).execute()
                    
                    logger.info(f"Updated scheduled call {call_id} with payment {razorpay_payment_id}")
            else:
                logger.info(f"No scheduled calls found with payment_id: {razorpay_payment_id}")
                
        except Exception as e:
            logger.error(f"Error updating scheduled calls by payment ID: {e}")

    async def _handle_call_payment_failure(self, razorpay_order_id: str):
        """Handle failed payment for call scheduling"""
        try:
            # Find scheduled call by razorpay_order_id
            result = self.supabase.table("scheduled_calls").select("*").eq(
                "razorpay_order_id", razorpay_order_id
            ).execute()
            
            if result.data:
                call_data = result.data[0]
                call_id = call_data["id"]
                
                # Update call with failed payment
                update_data = {
                    "payment_status": "failed",
                    "status": "cancelled",
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                self.supabase.table("scheduled_calls").update(update_data).eq("id", call_id).execute()
                
                logger.info(f"Call {call_id} cancelled due to failed payment")
                
        except Exception as e:
            logger.error(f"Error handling call payment failure: {e}")

    async def _send_calendar_invites_for_call(self, call_data: Dict[str, Any]):
        """Send calendar invites for a confirmed call"""
        try:
            from app.services.calendar.schedule_call_service import schedule_call_service
            
            # Create a ScheduleCallRequest object
            from app.models.models import ScheduleCallRequest
            from datetime import datetime
            
            request = ScheduleCallRequest(
                mentor_email=call_data["mentor_email"],
                start_time=datetime.fromisoformat(call_data["start_time"]),
                end_time=datetime.fromisoformat(call_data["end_time"]),
                title=call_data["title"],
                description=call_data.get("description"),
                notes=call_data.get("notes")
            )
            
            # Send calendar invites
            await schedule_call_service._send_calendar_invites(
                call_data["mentee_email"],
                call_data["mentor_email"],
                request,
                call_data["id"]
            )
            
        except Exception as e:
            logger.error(f"Error sending calendar invites for call: {e}")

    def _verify_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """Verify Razorpay webhook signature"""
        try:
            if not settings.razorpay_webhook_secret:
                return True  # Skip verification if webhook secret not configured
            
            received_signature = webhook_data.get("signature", "")
            payload = json.dumps(webhook_data, separators=(',', ':'))
            
            expected_signature = hmac.new(
                settings.razorpay_webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, received_signature)
        except Exception:
            return False

    def _verify_webhook_signature_from_body(self, body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature from raw body"""
        try:
            if not settings.razorpay_webhook_secret:
                return True  # Skip verification if webhook secret not configured
            
            expected_signature = hmac.new(
                settings.razorpay_webhook_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False

    def _get_currency_multiplier(self, currency: str) -> int:
        """Get the multiplier for currency to convert to smallest unit"""
        currency = currency.upper()
        
        # Currencies with 2 decimal places (most common)
        two_decimal_currencies = {
            'USD', 'EUR', 'GBP', 'AUD', 'CAD', 'CHF', 'JPY', 'SGD', 'HKD', 
            'NZD', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'BGN', 'RON',
            'HRK', 'TRY', 'RUB', 'BRL', 'MXN', 'ARS', 'CLP', 'COP', 'PEN',
            'UYU', 'VEF', 'ZAR', 'EGP', 'MAD', 'TND', 'DZD', 'NGN', 'KES',
            'UGX', 'TZS', 'ETB', 'GHS', 'XOF', 'XAF', 'AED', 'SAR', 'QAR',
            'KWD', 'BHD', 'OMR', 'JOD', 'LBP', 'ILS', 'PKR', 'BDT', 'LKR',
            'NPR', 'AFN', 'KZT', 'UZS', 'KGS', 'TJS', 'TMT', 'AZN', 'AMD',
            'GEL', 'MDL', 'BYN', 'UAH', 'KZT', 'MNT', 'KRW', 'THB', 'VND',
            'IDR', 'MYR', 'PHP', 'MMK', 'LAK', 'KHR', 'BND', 'FJD', 'PGK',
            'SBD', 'VUV', 'WST', 'TOP', 'XPF', 'NZD'
        }
        
        # Currencies with 0 decimal places
        zero_decimal_currencies = {
            'JPY', 'KRW', 'VND', 'IDR', 'CLP', 'PYG', 'RWF', 'UGX', 'VUV'
        }
        
        if currency in zero_decimal_currencies:
            return 1  # No decimal places
        elif currency in two_decimal_currencies:
            return 100  # 2 decimal places
        else:
            # Default to 2 decimal places for unknown currencies
            return 100


# Create service instance
payment_service = PaymentService()
