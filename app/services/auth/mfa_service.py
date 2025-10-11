"""
Firebase SMS and Email MFA Service
Handles SMS and Email Multi-Factor Authentication enrollment and verification
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from firebase_admin import auth
from app.core.database import get_supabase
from app.core.security import get_user_id_from_token
from app.services.email.email_service import email_service

logger = logging.getLogger(__name__)

class MFAService:
    """Service for handling Firebase SMS and Email MFA operations"""
    
    def __init__(self):
        self.supabase = get_supabase()
    
    async def enroll_sms_mfa(self, user_id: str, phone_number: str) -> Dict[str, Any]:
        """
        Enroll a user for SMS MFA
        
        Args:
            user_id: The user's ID from our database
            phone_number: Phone number in E.164 format (e.g., +1234567890)
            
        Returns:
            Dict containing enrollment result
        """
        try:
            # Get user's Firebase UID from our database
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                raise ValueError("User does not have Firebase UID")
            
            # Create phone auth provider
            phone_auth_provider = auth.PhoneAuthProvider()
            
            # Generate session info for phone verification
            session_info = phone_auth_provider.verify_phone_number(
                phone_number,
                app_verifier=None  # This will be handled by the client
            )
            
            # Store the session info temporarily in our database
            await self._store_mfa_session(user_id, {
                'phone_number': phone_number,
                'session_info': session_info,
                'status': 'pending_verification'
            })
            
            return {
                'success': True,
                'message': 'SMS verification code sent',
                'session_info': session_info,
                'phone_number': phone_number
            }
            
        except Exception as e:
            logger.error(f"Error enrolling SMS MFA: {str(e)}")
            raise ValueError(f"Failed to enroll SMS MFA: {str(e)}")
    
    async def verify_sms_mfa(self, user_id: str, verification_code: str, session_info: str) -> Dict[str, Any]:
        """
        Verify SMS MFA enrollment
        
        Args:
            user_id: The user's ID from our database
            verification_code: SMS verification code
            session_info: Session info from enrollment
            
        Returns:
            Dict containing verification result
        """
        try:
            # Get user's Firebase UID
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                raise ValueError("User does not have Firebase UID")
            
            # Verify the phone number with Firebase
            phone_auth_provider = auth.PhoneAuthProvider()
            credential = phone_auth_provider.credential(
                verification_id=session_info,
                verification_code=verification_code
            )
            
            # Link the phone credential to the user
            updated_user = auth.update_user(
                firebase_uid,
                multi_factor={
                    'enrolled_factors': [
                        {
                            'uid': f'phone_{firebase_uid}',
                            'display_name': 'Phone',
                            'phone_number': user_data.get('phone_number'),
                            'enrollment_time': auth.PhoneMultiFactorInfo()
                        }
                    ]
                }
            )
            
            # Update our database to mark MFA as enrolled
            await self._update_mfa_status(user_id, 'enrolled')
            
            return {
                'success': True,
                'message': 'SMS MFA successfully enrolled',
                'mfa_enrolled': True
            }
            
        except Exception as e:
            logger.error(f"Error verifying SMS MFA: {str(e)}")
            raise ValueError(f"Failed to verify SMS MFA: {str(e)}")
    
    async def enroll_email_mfa(self, user_id: str, email: str) -> Dict[str, Any]:
        """
        Enroll a user for Email MFA
        
        Args:
            user_id: The user's ID from our database
            email: Email address for MFA
            
        Returns:
            Dict containing enrollment result
        """
        try:
            # Get user's Firebase UID from our database
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                logger.error(f"User not found for user_id: {user_id}")
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                logger.error(f"User {user_id} does not have Firebase UID")
                raise ValueError("User does not have Firebase UID")
            
            logger.info(f"Attempting to send OTP email to {email} for user {user_id}")
            
            # Send OTP email
            result = email_service.send_otp_email(email, user_data.get('full_name'))
            
            if not result['success']:
                logger.error(f"Failed to send OTP email: {result['message']}")
                raise ValueError(f"Failed to send OTP email: {result['message']}")
            
            # Store the email MFA session temporarily
            await self._store_mfa_session(user_id, {
                'email': email,
                'mfa_type': 'email',
                'status': 'pending_verification'
            })
            
            logger.info(f"Email MFA enrollment initiated successfully for user {user_id}")
            
            return {
                'success': True,
                'message': 'Email verification code sent',
                'email': email,
                'mfa_type': 'email'
            }
            
        except Exception as e:
            logger.error(f"Error enrolling Email MFA for user {user_id}: {str(e)}")
            raise ValueError(f"Failed to enroll Email MFA: {str(e)}")
    
    async def verify_email_mfa(self, user_id: str, verification_code: str, email: str) -> Dict[str, Any]:
        """
        Verify Email MFA enrollment
        
        Args:
            user_id: The user's ID from our database
            verification_code: Email verification code
            email: Email address used for MFA
            
        Returns:
            Dict containing verification result
        """
        try:
            # Get user's Firebase UID
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                raise ValueError("User does not have Firebase UID")
            
            # Verify the OTP
            if not email_service.verify_otp(email, verification_code):
                raise ValueError("Invalid or expired verification code")
            
            # For email MFA, we'll store it in our database since Firebase doesn't have built-in email MFA
            # Update our database to mark email MFA as enrolled
            await self._update_email_mfa_status(user_id, email, 'enrolled')
            
            return {
                'success': True,
                'message': 'Email MFA successfully enrolled',
                'mfa_enrolled': True,
                'mfa_type': 'email'
            }
            
        except Exception as e:
            logger.error(f"Error verifying Email MFA: {str(e)}")
            raise ValueError(f"Failed to verify Email MFA: {str(e)}")
    
    async def check_mfa_status(self, user_id: str) -> Dict[str, Any]:
        """
        Check if user has MFA enrolled
        
        Args:
            user_id: The user's ID from our database
            
        Returns:
            Dict containing MFA status
        """
        try:
            # Get user's Firebase UID
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                return {'mfa_enrolled': False, 'message': 'No Firebase UID found'}
            
            # Check Firebase user's MFA status
            firebase_user = auth.get_user(firebase_uid)
            firebase_mfa_enrolled = len(firebase_user.multi_factor.enrolled_factors) > 0
            
            # Check email MFA status from our database
            email_mfa_data = await self._get_email_mfa_status(user_id)
            email_mfa_enrolled = email_mfa_data is not None
            
            # Combine both MFA types
            mfa_enrolled = firebase_mfa_enrolled or email_mfa_enrolled
            enrolled_factors = []
            
            # Add Firebase MFA factors
            if firebase_mfa_enrolled:
                for factor in firebase_user.multi_factor.enrolled_factors:
                    enrolled_factors.append({
                        'uid': factor.uid,
                        'display_name': factor.display_name,
                        'phone_number': getattr(factor, 'phone_number', None),
                        'enrollment_time': factor.enrollment_time.isoformat() if factor.enrollment_time else None,
                        'mfa_type': 'sms'
                    })
            
            # Add email MFA factor
            if email_mfa_enrolled:
                enrolled_factors.append({
                    'uid': f'email_{user_id}',
                    'display_name': 'Email',
                    'email': email_mfa_data.get('email'),
                    'enrollment_time': email_mfa_data.get('enrolled_at'),
                    'mfa_type': 'email'
                })
            
            return {
                'mfa_enrolled': mfa_enrolled,
                'enrolled_factors': enrolled_factors
            }
            
        except Exception as e:
            logger.error(f"Error checking MFA status: {str(e)}")
            return {'mfa_enrolled': False, 'error': str(e)}
    
    async def disable_mfa(self, user_id: str) -> Dict[str, Any]:
        """
        Disable MFA for a user
        
        Args:
            user_id: The user's ID from our database
            
        Returns:
            Dict containing disable result
        """
        try:
            # Get user's Firebase UID
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                raise ValueError("User does not have Firebase UID")
            
            # Disable MFA in Firebase
            auth.update_user(
                firebase_uid,
                multi_factor={
                    'enrolled_factors': []
                }
            )
            
            # Update our database
            await self._update_mfa_status(user_id, 'disabled')
            
            return {
                'success': True,
                'message': 'MFA successfully disabled',
                'mfa_enrolled': False
            }
            
        except Exception as e:
            logger.error(f"Error disabling MFA: {str(e)}")
            raise ValueError(f"Failed to disable MFA: {str(e)}")
    
    async def _get_user_firebase_uid(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's Firebase UID from our database"""
        try:
            result = self.supabase.table("users").select("firebase_uid, full_name").eq("user_id", user_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting user Firebase UID: {str(e)}")
            return None
    
    async def _store_mfa_session(self, user_id: str, session_data: Dict[str, Any]) -> None:
        """Store MFA session data temporarily"""
        try:
            # Store in a temporary table or use Redis for session storage
            # For now, we'll use a simple approach with the users table
            update_data = {
                'mfa_session_data': session_data,
                'updated_at': 'now()'
            }
            self.supabase.table("users").update(update_data).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Error storing MFA session: {str(e)}")
    
    async def _update_mfa_status(self, user_id: str, status: str) -> None:
        """Update MFA status in database"""
        try:
            update_data = {
                'mfa_status': status,
                'mfa_enrolled_at': 'now()' if status == 'enrolled' else None,
                'updated_at': 'now()'
            }
            self.supabase.table("users").update(update_data).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Error updating MFA status: {str(e)}")
    
    async def _update_email_mfa_status(self, user_id: str, email: str, status: str) -> None:
        """Update email MFA status in database"""
        try:
            update_data = {
                'email_mfa_status': status,
                'email_mfa_email': email if status == 'enrolled' else None,
                'email_mfa_enrolled_at': 'now()' if status == 'enrolled' else None,
                'updated_at': 'now()'
            }
            self.supabase.table("users").update(update_data).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Error updating email MFA status: {str(e)}")
    
    async def _get_email_mfa_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get email MFA status from database"""
        try:
            result = self.supabase.table("users").select("email_mfa_status, email_mfa_email, email_mfa_enrolled_at").eq("user_id", user_id).execute()
            if result.data and result.data[0].get('email_mfa_status') == 'enrolled':
                return {
                    'email': result.data[0].get('email_mfa_email'),
                    'enrolled_at': result.data[0].get('email_mfa_enrolled_at')
                }
            return None
        except Exception as e:
            logger.error(f"Error getting email MFA status: {str(e)}")
            return None
    
    async def initiate_mfa_signin(self, user_id: str) -> Dict[str, Any]:
        """
        Initiate MFA sign-in process
        
        Args:
            user_id: The user's ID from our database
            
        Returns:
            Dict containing MFA challenge info
        """
        try:
            # Get user's Firebase UID
            user_data = await self._get_user_firebase_uid(user_id)
            if not user_data:
                raise ValueError("User not found")
            
            firebase_uid = user_data.get('firebase_uid')
            if not firebase_uid:
                raise ValueError("User does not have Firebase UID")
            
            # Check if user has MFA enrolled
            firebase_user = auth.get_user(firebase_uid)
            if not firebase_user.multi_factor.enrolled_factors:
                return {
                    'mfa_required': False,
                    'message': 'User does not have MFA enrolled'
                }
            
            # Generate MFA challenge
            # This would typically be handled by the client-side Firebase SDK
            # We'll return the enrolled factors for the client to handle
            return {
                'mfa_required': True,
                'enrolled_factors': [
                    {
                        'uid': factor.uid,
                        'display_name': factor.display_name,
                        'phone_number': getattr(factor, 'phone_number', None)
                    }
                    for factor in firebase_user.multi_factor.enrolled_factors
                ]
            }
            
        except Exception as e:
            logger.error(f"Error initiating MFA signin: {str(e)}")
            raise ValueError(f"Failed to initiate MFA signin: {str(e)}")

# Create a singleton instance
mfa_service = MFAService()
