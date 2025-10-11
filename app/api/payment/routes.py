from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional
import logging
from datetime import datetime
from app.core.security.auth_dependencies import get_current_user
from app.models.models import TokenData
from app.models.models import (
    PaymentCreate, PaymentResponse, PaymentVerificationRequest, 
    RefundCreate, RefundResponse, PaymentSummary, PaymentWebhookData,
    SuccessResponse, ErrorResponse
)
from app.services.payment.payment_service import payment_service
from app.core.database import get_supabase

router = APIRouter(prefix="/payment", tags=["payment"])
logger = logging.getLogger(__name__)


@router.post("/create-order", response_model=dict)
async def create_payment_order(
    payment_data: PaymentCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new payment order"""
    try:
        mentee_id = current_user.user_id
        result = await payment_service.create_payment_order(payment_data, mentee_id)
        return {
            "success": True,
            "message": "Payment order created successfully",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/verify", response_model=dict)
async def verify_payment(
    payment_id: str,
    verification_data: PaymentVerificationRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Verify payment after successful payment"""
    try:
        # Verify that the payment belongs to the current user
        supabase = get_supabase()
        result = supabase.table("payments").select("mentee_id").eq("id", payment_id).execute()
        
        if not result.data or result.data[0]["mentee_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment not found or access denied"
            )
        
        payment_response = await payment_service.verify_payment(
            payment_id, 
            verification_data.dict()
        )
        
        return {
            "success": True,
            "message": "Payment verified successfully",
            "data": payment_response.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{payment_id}", response_model=dict)
async def get_payment(
    payment_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get payment details by ID"""
    try:
        # Verify that the payment belongs to the current user
        supabase = get_supabase()
        result = supabase.table("payments").select("mentee_id, mentor_id").eq("id", payment_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment_data = result.data[0]
        if payment_data["mentee_id"] != current_user.user_id and payment_data["mentor_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        payment_response = await payment_service.get_payment_by_id(payment_id)
        
        return {
            "success": True,
            "message": "Payment retrieved successfully",
            "data": payment_response.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=dict)
async def get_user_payments(
    limit: int = 20,
    offset: int = 0,
    current_user: TokenData = Depends(get_current_user)
):
    """Get all payments for the current user"""
    try:
        user_id = current_user.user_id
        payments = await payment_service.get_user_payments(user_id, limit, offset)
        
        return {
            "success": True,
            "message": "Payments retrieved successfully",
            "data": {
                "payments": [payment.dict() for payment in payments],
                "total": len(payments)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/summary/overview", response_model=dict)
async def get_payment_summary(
    current_user: TokenData = Depends(get_current_user)
):
    """Get payment summary for the current user"""
    try:
        user_id = current_user.user_id
        summary = await payment_service.get_payment_summary(user_id)
        
        return {
            "success": True,
            "message": "Payment summary retrieved successfully",
            "data": summary.dict()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/refund", response_model=dict)
async def create_refund(
    refund_data: RefundCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a refund for a payment"""
    try:
        # Verify that the payment belongs to the current user
        supabase = get_supabase()
        result = supabase.table("payments").select("mentee_id, mentor_id").eq("id", refund_data.payment_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment_data = result.data[0]
        if payment_data["mentee_id"] != current_user.user_id and payment_data["mentor_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        refund_response = await payment_service.create_refund(refund_data)
        
        return {
            "success": True,
            "message": "Refund created successfully",
            "data": refund_response.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/webhook")
async def handle_webhook(request: Request):
    """Handle Razorpay webhook events"""
    try:
        # Get raw body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Parse webhook data
        import json
        webhook_data = json.loads(body.decode())
        
        # Add signature from headers
        webhook_data["signature"] = headers.get("x-razorpay-signature", "")
        
        # Handle webhook
        success = await payment_service.handle_webhook(webhook_data)
        
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.get("/config/razorpay", response_model=dict)
async def get_razorpay_config():
    """Get Razorpay configuration for frontend"""
    from app.core.config import settings
    
    return {
        "success": True,
        "message": "Razorpay configuration retrieved successfully",
        "data": {
            "key_id": settings.razor_pay_key_id,
            "supported_currencies": [
                "INR", "USD", "EUR", "GBP", "AUD", "CAD", "CHF", "SGD", 
                "HKD", "NZD", "SEK", "NOK", "DKK", "AED", "SAR", "QAR",
                "KWD", "BHD", "OMR", "JOD", "ILS", "PKR", "BDT", "LKR",
                "NPR", "KZT", "UZS", "KGS", "KRW", "THB", "VND", "IDR",
                "MYR", "PHP", "MMK", "LAK", "KHR", "BND", "FJD", "PGK"
            ],
            "default_currency": "INR"
        }
    }

@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhook events"""
    try:
        # Get the raw body
        body = await request.body()
        
        # Get the signature from headers
        signature = request.headers.get("X-Razorpay-Signature", "")
        
        # Verify webhook signature
        if not payment_service._verify_webhook_signature_from_body(body, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        
        # Parse the webhook data
        webhook_data = await request.json()
        # Mark as pre-verified to skip internal verification
        webhook_data["__preverified"] = True
        
        # Handle the webhook event
        success = await payment_service.handle_webhook(webhook_data)
        
        if success:
            return {"status": "success", "message": "Webhook processed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process webhook"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


# Additional utility endpoints

@router.get("/mentor/{mentor_id}/payments", response_model=dict)
async def get_mentor_payments(
    mentor_id: str,
    limit: int = 20,
    offset: int = 0,
    current_user: TokenData = Depends(get_current_user)
):
    """Get payments for a specific mentor (for mentor dashboard)"""
    try:
        # Verify that the current user is the mentor
        if current_user.user_id != mentor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        supabase = get_supabase()
        result = supabase.table("payments").select(
            "*, mentee:mentee_id(*), mentor:mentor_id(*)"
        ).eq("mentor_id", mentor_id).order(
            "created_at", desc=True
        ).range(offset, offset + limit - 1).execute()
        
        if not result.data:
            return {
                "success": True,
                "message": "No payments found",
                "data": {"payments": [], "total": 0}
            }
        
        payments = []
        for payment in result.data:
            mentee_data = payment.get("mentee", {})
            mentor_data = payment.get("mentor", {})
            
            payments.append({
                "id": payment["id"],
                "amount": payment["amount"],
                "currency": payment["currency"],
                "status": payment["status"],
                "payment_method": payment.get("payment_method"),
                "mentee_name": f"{mentee_data.get('first_name', '')} {mentee_data.get('last_name', '')}".strip(),
                "mentee_email": mentee_data.get("email"),
                "description": payment.get("description"),
                "created_at": payment["created_at"],
                "updated_at": payment["updated_at"]
            })
        
        return {
            "success": True,
            "message": "Mentor payments retrieved successfully",
            "data": {
                "payments": payments,
                "total": len(payments)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/session/{session_id}/payment", response_model=dict)
async def update_session_payment(
    session_id: str,
    payment_data: dict,
    current_user: TokenData = Depends(get_current_user)
):
    """Update payment details for a specific session"""
    try:
        supabase = get_supabase()
        
        # Verify the session belongs to the current user
        session_result = supabase.table("session_payments").select("mentee_id, mentor_id").eq("session_id", session_id).execute()
        
        if not session_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session payment not found"
            )
        
        payment_record = session_result.data[0]
        if payment_record["mentee_id"] != current_user.user_id and payment_record["mentor_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Prepare update data
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Add fields if provided
        if "razorpay_payment_id" in payment_data:
            update_data["razorpay_payment_id"] = payment_data["razorpay_payment_id"]
        
        if "status" in payment_data:
            update_data["status"] = payment_data["status"]
        
        if "razorpay_signature" in payment_data:
            update_data["razorpay_signature"] = payment_data["razorpay_signature"]
        
        if "payment_method" in payment_data:
            update_data["payment_method"] = payment_data["payment_method"]
        
        if "captured_at" in payment_data:
            update_data["captured_at"] = payment_data["captured_at"]
        
        # Update the payment record
        result = supabase.table("session_payments").update(update_data).eq("session_id", session_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update payment"
            )
        
        return {
            "success": True,
            "message": "Payment updated successfully",
            "data": result.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment: {str(e)}"
        )


@router.get("/session/{session_id}/payment", response_model=dict)
async def get_session_payment(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get payment details for a specific session"""
    try:
        supabase = get_supabase()
        # Use session_payments table for session-specific payments
        result = supabase.table("session_payments").select(
            "*, mentee:mentee_id(*), mentor:mentor_id(*)"
        ).eq("session_id", session_id).execute()
        
        if not result.data:
            return {
                "success": True,
                "message": "No payment found for this session",
                "data": None
            }
        
        payment = result.data[0]
        
        # Verify access
        if payment["mentee_id"] != current_user.user_id and payment["mentor_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        mentee_data = payment.get("mentee", {})
        mentor_data = payment.get("mentor", {})
        
        payment_response = {
            "id": payment["id"],
            "amount": payment["amount"],
            "currency": payment["currency"],
            "status": payment["status"],
            "payment_method": payment.get("payment_method"),
            "mentee_name": f"{mentee_data.get('first_name', '')} {mentee_data.get('last_name', '')}".strip() if mentee_data else None,
            "mentee_email": mentee_data.get("email") if mentee_data else None,
            "mentor_name": f"{mentor_data.get('first_name', '')} {mentor_data.get('last_name', '')}".strip() if mentor_data else None,
            "mentor_email": mentor_data.get("email") if mentor_data else None,
            "description": payment.get("description"),
            "created_at": payment["created_at"],
            "updated_at": payment["updated_at"]
        }
        
        return {
            "success": True,
            "message": "Session payment retrieved successfully",
            "data": payment_response
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
