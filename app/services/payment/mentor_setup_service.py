import logging
import uuid
import requests
import base64
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status

from app.core.database import get_supabase
from app.core.config import settings
from app.models.models import MentorSetupRequest, MentorSetupResponse

logger = logging.getLogger(__name__)

class MentorSetupService:
    def __init__(self):
        self.supabase = get_supabase()
        
        # Initialize Razorpay API credentials
        self.base_url = "https://api.razorpay.com/v2"
        if not settings.razor_pay_key_id or not settings.razor_pay_key_seceret:
            # Do NOT crash the app at import time; mark service disabled
            logger.warning("Razorpay credentials not configured; mentor setup service disabled")
            self.enabled = False
            self.key_id = None
            self.key_secret = None
            self.headers = {"Content-Type": "application/json"}
        else:
            self.enabled = True
            self.key_id = settings.razor_pay_key_id
            self.key_secret = settings.razor_pay_key_seceret
            # Create basic auth header
            credentials = f"{self.key_id}:{self.key_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }

    async def setup_mentor(
        self, 
        user_id: str, 
        setup_data: MentorSetupRequest
    ) -> MentorSetupResponse:
        """Setup mentor with Razorpay Linked Account"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            logger.info(f"Setting up mentor for user: {user_id}")

            # Check if mentor already exists
            existing = await self.get_mentor_by_user_id(user_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mentor already exists for this user"
                )

            # Get user details
            user_result = self.supabase.table("users").select("email").eq("user_id", user_id).execute()
            if not user_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            user_email = user_result.data[0]["email"]

            # Create Razorpay Linked Account (Route style with bank details)
            razorpay_account = await self._create_razorpay_account(user_id, setup_data, user_email)

            # Update bank_details with Razorpay account ID
            update_data = {
                "razorpay_account_id": razorpay_account["id"],
                "razorpay_route_account_id": razorpay_account.get("id"),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("bank_details").update(update_data).eq("user_id", user_id).execute()

            if not result.data:
                # If database update fails, we should ideally clean up Razorpay account
                logger.error(f"Failed to update bank_details for user: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update bank details with Razorpay account"
                )

            # Return mentor setup response
            return MentorSetupResponse(
                id=result.data[0]["id"],
                user_id=user_id,
                razorpay_account_id=razorpay_account["id"],
                is_payout_ready=True,
                kyc_status="pending",
                created_at=datetime.fromisoformat(result.data[0]["created_at"]),
                updated_at=datetime.fromisoformat(result.data[0]["updated_at"])
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error setting up mentor: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to setup mentor: {str(e)}"
            )

    async def get_mentor_by_user_id(self, user_id: str) -> Optional[MentorSetupResponse]:
        """Get mentor by user ID from bank_details"""
        try:
            result = self.supabase.table("bank_details").select("*").eq("user_id", user_id).execute()

            if not result.data:
                return None

            bank_details = result.data[0]
            # Check if Razorpay account is configured
            is_setup = bool(bank_details.get("razorpay_account_id") or bank_details.get("razorpay_route_account_id"))
            
            return MentorSetupResponse(
                id=bank_details["id"],
                user_id=user_id,
                razorpay_account_id=bank_details.get("razorpay_account_id"),
                is_payout_ready=is_setup,
                kyc_status="pending",  # Default since KYC is not tracked
                created_at=datetime.fromisoformat(bank_details["created_at"]),
                updated_at=datetime.fromisoformat(bank_details["updated_at"])
            )

        except Exception as e:
            logger.error(f"Error getting mentor: {e}")
            return None

    async def _create_razorpay_account(
        self,
        user_id: str,
        setup_data: MentorSetupRequest,
        user_email: str,
    ) -> Dict[str, Any]:
        """Create Razorpay Linked Account using Route payload including bank details"""
        try:
            if not self.enabled:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Razorpay not configured on this deployment"
                )
            # Use Razorpay Route endpoint for creating route accounts
            url = "https://api.razorpay.com/v1/route/accounts"

            # Fetch bank details for bank_account section
            bank = None
            try:
                bank_res = self.supabase.table("bank_details").select(
                    "branch_ifsc_code,account_number,beneficiary_name"
                ).eq("user_id", user_id).execute()
                if bank_res.data:
                    bank = bank_res.data[0]
            except Exception:
                bank = None

            country = (setup_data.address or {}).get("country", "IN")
            addr = setup_data.address or {}

            payload = {
                "type": "route",
                "reference_id": f"mentor_{user_id}",
                "name": setup_data.contact_name or setup_data.business_name,
                "email": setup_data.contact_email or user_email,
                "contact": {
                    "name": setup_data.contact_name or setup_data.business_name,
                    "email": setup_data.contact_email or user_email,
                    "contact": setup_data.contact_mobile or ""
                },
                "business_type": setup_data.business_type,
                "business_name": setup_data.business_name,
                "legal_business_name": setup_data.contact_name or setup_data.business_name,
                "profile": {
                    "category": "others",
                    "subcategory": "others",
                    "description": "Consulting services"
                },
                "bank_account": {
                    "ifsc_code": (bank or {}).get("branch_ifsc_code"),
                    "account_number": (bank or {}).get("account_number"),
                    "beneficiary_name": (bank or {}).get("beneficiary_name"),
                },
                "registered_address": {
                    "street": addr.get("street", "N/A"),
                    "city": addr.get("city", "N/A"),
                    "state": addr.get("state", "N/A"),
                    "postal_code": addr.get("postal_code", "000000"),
                    "country": addr.get("country", country),
                },
            }

            # Remove None/empty values shallowly
            payload = {k: v for k, v in payload.items() if v is not None}
 
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
             
            result = response.json()
            logger.info(f"Created Razorpay account: {result['id']}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Razorpay API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create Razorpay account: {str(e)}"
            )

    async def update_kyc_status(self, razorpay_account_id: str, status: str):
        """Update KYC status from Razorpay webhook"""
        try:
            update_data = {
                "kyc_status": status,
                "updated_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("mentors").update(update_data).eq(
                "razorpay_account_id", razorpay_account_id
            ).execute()

            if result.data:
                logger.info(f"Updated KYC status for account {razorpay_account_id} to {status}")

        except Exception as e:
            logger.error(f"Error updating KYC status: {e}")

    async def get_razorpay_account_details(self, razorpay_account_id: str) -> Dict[str, Any]:
        """Fetch linked account details from Razorpay"""
        try:
            url = f"{self.base_url}/accounts/{razorpay_account_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Razorpay API error (get account {razorpay_account_id}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch linked account from Razorpay"
            )


# Create service instance
mentor_setup_service = MentorSetupService()
