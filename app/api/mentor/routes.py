from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from app.core.security.auth_dependencies import get_current_user
from app.models.models import (
    MentorSetupRequest, MentorSetupResponse, SimpleMentorSetupRequest,
    MentorDetailsCreate, MentorDetailsUpdate, MentorDetailsResponse,
    BankDetailsCreate,
    SessionCreateRequest, SessionResponse, SessionPaymentRequest, SessionPaymentResponse,
    TransferRequest, TransferResponse, SuccessResponse, ErrorResponse,
    MentorDashboardResponse, MentorshipInterestResponse
)
from app.services.payment.mentor_setup_service import mentor_setup_service
from app.services.payment.session_payment_service import session_payment_service
from app.services.payment.bank_details_service import bank_details_service
from app.services.user.services import mentor_service, mentorship_interest_service

router = APIRouter(prefix="/mentors", tags=["mentors"])
logger = logging.getLogger(__name__)

@router.post("/{mentor_id}/setup", response_model=dict)
async def setup_mentor(
    mentor_id: str,
    setup_data: MentorSetupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Setup mentor with Razorpay Linked Account"""
    try:
        # Resolve user_id robustly from token (object or dict)
        current_user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not current_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Verify the user is setting up their own mentor account
        if current_user_id != mentor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only setup your own mentor account"
            )

        result = await mentor_setup_service.setup_mentor(mentor_id, setup_data)
        
        return {
            "success": True,
            "message": "Mentor setup completed successfully",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mentor setup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup mentor"
        )

@router.post("/setup-simple", response_model=dict)
async def setup_mentor_simple(
    setup_data: SimpleMentorSetupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Setup mentor using 7 simple fields; user_id from JWT"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            logger.error("setup-simple: missing user_id in token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        logger.info(f"setup-simple: user_id={user_id} email={getattr(current_user, 'email', None)}")

        # 1) Save simplified bank details mapped to our simple table
        await bank_details_service.create_bank_details(
            user_id,
            bank_data=BankDetailsCreate(
                account_name=setup_data.account_name,
                account_email=setup_data.account_email,
                business_name=setup_data.business_name,
                business_type=setup_data.business_type,
                branch_ifsc_code=setup_data.branch_ifsc_code,
                account_number=setup_data.account_number,
                beneficiary_name=setup_data.beneficiary_name
            )
        )

        # 2) Create Linked Account (acc_XXXX) via mentor_setup_service using minimal payload
        # We will pass business_name/business_type and derive contact from current_user (email/name if available)
        minimal_request = MentorSetupRequest(
            business_name=setup_data.business_name,
            business_type=setup_data.business_type,
            business_registration_number=None,
            business_pan=None,
            business_gst=None,
            contact_name=setup_data.account_name,
            contact_email=setup_data.account_email,
            contact_mobile="",
            address={"country": "IN"}
        )

        mentor_record = await mentor_setup_service.setup_mentor(user_id, minimal_request)

        return {
            "success": True,
            "message": "Mentor setup (simple) completed",
            "data": mentor_record
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in simple mentor setup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup mentor (simple)"
        )

@router.get("/{mentor_id}/status", response_model=dict)
async def get_mentor_status(
    mentor_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get mentor setup status"""
    try:
        # Check bank_details for mentor setup status
        bank_result = bank_details_service.get_bank_details_by_user_id(mentor_id)
        
        if not bank_result:
            return {
                "success": True,
                "message": "Mentor not setup",
                "data": None
            }

        # Check if Razorpay account is configured
        is_setup = bool(bank_result.razorpay_account_id or bank_result.razorpay_route_account_id)
        
        return {
            "success": True,
            "message": "Mentor status retrieved successfully",
            "data": {
                "user_id": mentor_id,
                "is_payout_ready": is_setup,
                "razorpay_account_id": bank_result.razorpay_account_id,
                "razorpay_route_account_id": bank_result.razorpay_route_account_id
            }
        }

    except Exception as e:
        logger.error(f"Error getting mentor status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mentor status"
        )

@router.get("/linked-account", response_model=dict)
async def get_linked_account_details(
    current_user: dict = Depends(get_current_user)
):
    """Fetch current user's linked account details from Razorpay"""
    try:
        user_id = getattr(current_user, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Fetch bank details to get razorpay_account_id
        bank_details = await bank_details_service.get_bank_details_by_user_id(user_id)
        if not bank_details or not (bank_details.razorpay_account_id or bank_details.razorpay_route_account_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked account not found")

        # Use the available account ID
        account_id = bank_details.razorpay_route_account_id or bank_details.razorpay_account_id
        details = await mentor_setup_service.get_razorpay_account_details(account_id)

        return {
            "success": True,
            "message": "Linked account details fetched",
            "data": details
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching linked account details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch linked account details")

@router.post("/details", response_model=MentorDetailsResponse)
async def create_mentor_details(
    mentor_data: MentorDetailsCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create mentor details"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Ensure the user_id matches the authenticated user
        if mentor_data.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create details for another user"
            )
        
        mentor_details = await mentor_service.create_mentor_details(mentor_data)
        return mentor_details
        
    except HTTPException:
        raise
    except Exception as e:
        if "already exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mentor details already exist for this user"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create mentor details"
        )

@router.get("/details", response_model=MentorDetailsResponse)
async def get_mentor_details(current_user: dict = Depends(get_current_user)):
    """Get mentor details for current user"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        mentor_details = await mentor_service.get_mentor_details_by_user_id(user_id)
        if not mentor_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor details not found"
            )
        return mentor_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mentor details"
        )

@router.put("/details", response_model=MentorDetailsResponse)
async def update_mentor_details(
    update_data: MentorDetailsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update mentor details"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        mentor_details = await mentor_service.update_mentor_details(user_id, update_data)
        if not mentor_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mentor details not found"
            )
        return mentor_details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mentor details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update mentor details"
        )

@router.post("/sessions", response_model=dict)
async def create_session(
    session_data: SessionCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new session (mentee creates session with mentor)"""
    try:
        mentee_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not mentee_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        result = await session_payment_service.create_session(mentee_id, session_data)
        
        return {
            "success": True,
            "message": "Session created successfully",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

@router.post("/sessions/{session_id}/pay", response_model=dict)
async def pay_for_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Create payment order for session"""
    try:
        mentee_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not mentee_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        payment_data = SessionPaymentRequest(session_id=session_id)
        result = await session_payment_service.create_payment_order(mentee_id, payment_data)
        
        return {
            "success": True,
            "message": "Payment order created successfully",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order"
        )

@router.post("/transfers/{payment_id}", response_model=dict)
async def process_transfer(
    payment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Process transfer to mentor (70% payout)"""
    try:
        # This endpoint should be called by admin/system, not regular users
        # For now, allowing any authenticated user for testing
        transfer_data = TransferRequest(payment_id=payment_id)
        result = await session_payment_service.process_transfer(transfer_data)
        
        return {
            "success": True,
            "message": "Transfer processed successfully",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process transfer"
        )

@router.get("/dashboard", response_model=MentorDashboardResponse)
async def get_mentor_dashboard(current_user: dict = Depends(get_current_user)):
    """Get mentor dashboard with total mentees, sessions, earnings, and reviews"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        dashboard_data = await mentor_service.get_mentor_dashboard(user_id)
        return dashboard_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mentor dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mentor dashboard"
        )

@router.get("/all-interests", response_model=List[MentorshipInterestResponse])
async def get_all_mentorship_interests(current_user: dict = Depends(get_current_user)):
    """Get all mentorship interests received by the current mentor"""
    try:
        # Resolve user_id robustly from token
        user_id = (
            getattr(current_user, "user_id", None)
            or getattr(current_user, "sub", None)
            or (current_user.get("user_id") if isinstance(current_user, dict) else None)
        )
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        interests = await mentorship_interest_service.get_interests_by_mentor(user_id)
        return interests
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mentorship interests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mentorship interests"
        )