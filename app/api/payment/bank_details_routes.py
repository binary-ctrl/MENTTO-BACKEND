from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional

from app.core.security.auth_dependencies import get_current_user
from app.models.models import (
    BankDetailsCreate, BankDetailsUpdate, BankDetailsResponse,
    SuccessResponse, ErrorResponse
)
from app.services.payment.bank_details_service import bank_details_service

router = APIRouter(prefix="/bank-details", tags=["bank-details"])

@router.post("/", response_model=BankDetailsResponse)
async def create_bank_details(
    bank_data: BankDetailsCreate,
    current_user = Depends(get_current_user)
):
    """Create bank details for the current user"""
    try:
        result = await bank_details_service.create_bank_details(
            user_id=str(current_user.user_id),
            bank_data=bank_data
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bank details: {str(e)}"
        )

@router.get("/", response_model=BankDetailsResponse | ErrorResponse)
async def get_bank_details(
    current_user = Depends(get_current_user)
):
    """Get bank details for the current user"""
    try:
        result = await bank_details_service.get_bank_details_by_user_id(str(current_user.user_id))
        
        if not result:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=ErrorResponse(
                    message="No bank details found for the current user.",
                    error_code="BANK_DETAILS_NOT_FOUND"
                ).model_dump()
            )
        
        return result

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                message="Failed to get bank details. Please try again later.",
                error_code="BANK_DETAILS_FETCH_ERROR"
            ).model_dump()
        )

@router.put("/", response_model=BankDetailsResponse)
async def update_bank_details(
    bank_data: BankDetailsUpdate,
    current_user = Depends(get_current_user)
):
    """Update bank details for the current user"""
    try:
        result = await bank_details_service.update_bank_details(
            user_id=str(current_user.user_id),
            bank_data=bank_data
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bank details: {str(e)}"
        )

@router.delete("/")
async def delete_bank_details(
    current_user = Depends(get_current_user)
):
    """Delete bank details for the current user"""
    try:
        success = await bank_details_service.delete_bank_details(str(current_user.user_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank details not found"
            )
        
        return SuccessResponse(
            message="Bank details deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete bank details: {str(e)}"
        )

@router.post("/verify", response_model=BankDetailsResponse)
async def verify_bank_details(
    current_user = Depends(get_current_user)
):
    """Verify bank details with Razorpay"""
    try:
        result = await bank_details_service.verify_bank_details(str(current_user.user_id))
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify bank details: {str(e)}"
        )
