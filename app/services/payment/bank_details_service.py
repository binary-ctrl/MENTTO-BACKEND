import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from fastapi import HTTPException, status

from app.core.database import get_supabase
from app.models.models import (
    BankDetailsCreate, BankDetailsUpdate, BankDetailsResponse, BankAccountType
)

logger = logging.getLogger(__name__)

class BankDetailsService:
    def __init__(self):
        self.supabase = get_supabase()

    async def create_bank_details(
        self, 
        user_id: str, 
        bank_data: BankDetailsCreate
    ) -> BankDetailsResponse:
        """Create bank details for a user"""
        try:
            logger.info(f"Creating bank details for user: {user_id}")

            # Check if user already has bank details
            existing = await self.get_bank_details_by_user_id(user_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bank details already exist for this user"
                )

            # Generate a unique account number if not provided
            account_number = bank_data.account_number or str(uuid.uuid4().int)[:10]

            # Create bank details record
            # Handle empty email - use a placeholder or None if required
            account_email = bank_data.account_email if bank_data.account_email else None
            
            bank_record = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "account_name": bank_data.account_name,
                "account_email": account_email,
                "business_name": bank_data.business_name,
                "business_type": bank_data.business_type,
                "branch_ifsc_code": bank_data.branch_ifsc_code.upper(),
                "account_number": account_number,
                "beneficiary_name": bank_data.beneficiary_name,
                "pan_number": bank_data.pan_number.upper(),
                "phone_number": bank_data.phone_number,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("bank_details").insert(bank_record).execute()

            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create bank details"
                )

            return BankDetailsResponse.model_validate(result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating bank details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create bank details: {str(e)}"
            )

    async def get_bank_details_by_user_id(self, user_id: str) -> Optional[BankDetailsResponse]:
        """Get bank details by user ID"""
        try:
            result = self.supabase.table("bank_details").select("*").eq("user_id", user_id).execute()

            if not result.data:
                return None

            return BankDetailsResponse.model_validate(result.data[0])

        except Exception as e:
            logger.error(f"Error getting bank details: {e}")
            return None

    async def update_bank_details(
        self, 
        user_id: str, 
        bank_data: BankDetailsUpdate
    ) -> BankDetailsResponse:
        """Update bank details for a user"""
        try:
            logger.info(f"Updating bank details for user: {user_id}")

            # Check if bank details exist
            existing = await self.get_bank_details_by_user_id(user_id)
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank details not found for this user"
                )

            # Prepare update data
            update_data = {}
            if bank_data.account_name is not None:
                update_data["account_name"] = bank_data.account_name
            if bank_data.account_email is not None:
                update_data["account_email"] = bank_data.account_email
            if bank_data.business_name is not None:
                update_data["business_name"] = bank_data.business_name
            if bank_data.business_type is not None:
                update_data["business_type"] = bank_data.business_type
            if bank_data.branch_ifsc_code is not None:
                update_data["branch_ifsc_code"] = bank_data.branch_ifsc_code.upper()
            if bank_data.account_number is not None:
                update_data["account_number"] = bank_data.account_number
            if bank_data.beneficiary_name is not None:
                update_data["beneficiary_name"] = bank_data.beneficiary_name
            if bank_data.pan_number is not None:
                update_data["pan_number"] = bank_data.pan_number.upper()
            if bank_data.phone_number is not None:
                update_data["phone_number"] = bank_data.phone_number

            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )

            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow().isoformat()

            result = self.supabase.table("bank_details").update(update_data).eq("user_id", user_id).execute()

            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update bank details"
                )

            return BankDetailsResponse.model_validate(result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating bank details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update bank details: {str(e)}"
            )

    async def delete_bank_details(self, user_id: str) -> bool:
        """Delete bank details for a user"""
        try:
            logger.info(f"Deleting bank details for user: {user_id}")

            result = self.supabase.table("bank_details").delete().eq("user_id", user_id).execute()

            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error deleting bank details: {e}")
            return False

    async def verify_bank_details(self, user_id: str) -> BankDetailsResponse:
        """Verify bank details (placeholder for future verification logic)"""
        try:
            logger.info(f"Verifying bank details for user: {user_id}")

            # Get bank details
            bank_details = await self.get_bank_details_by_user_id(user_id)
            if not bank_details:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank details not found"
                )

            # For now, just return the bank details
            # In the future, this could integrate with verification services
            return bank_details

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error verifying bank details: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify bank details: {str(e)}"
            )


# Create service instance
bank_details_service = BankDetailsService()