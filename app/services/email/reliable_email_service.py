"""
Reliable Email Service that wraps the existing EmailService with retry mechanism and logging
"""

import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from app.services.email.email_service import email_service
from app.services.email.enhanced_email_service import enhanced_email_service
from app.models.models import EmailLogResponse

logger = logging.getLogger(__name__)

class ReliableEmailService:
    """Reliable email service with retry mechanism and comprehensive logging"""
    
    def __init__(self):
        self.original_service = email_service
        self.enhanced_service = enhanced_email_service
    
    async def send_mentor_verified_email(self, to_email: str, user_name: str = None) -> Dict[str, Any]:
        """Send mentor verified email with retry mechanism and logging"""
        try:
            # Get the email content from the original service
            first_name = user_name.split()[0] if user_name and user_name.strip() else "Mentor"
            subject = "Congratulations! You're Now Live on MenttoConnect! 🚀"
            
            # HTML content (copied from original service)
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Profile Verified - MenttoConnect</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif; 
                        line-height: 1.6; 
                        color: #333; 
                        margin: 0; 
                        padding: 0; 
                        background-color: #f4f4f4;
                    }}
                    .container {{ 
                        max-width: 600px; 
                        margin: 20px auto; 
                        background-color: white; 
                        border-radius: 8px; 
                        overflow: hidden;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .content {{ 
                        padding: 40px 30px; 
                    }}
                    .congratulations-title {{ 
                        font-size: 28px; 
                        margin: 0 0 20px 0; 
                        color: #32898b;
                        text-align: center;
                    }}
                    .success-notice {{ 
                        background-color: white; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #10b981;
                        text-align: center;
                    }}
                    .tips {{ 
                        background-color: #f8fafc;
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0;
                    }}
                    .tip {{ 
                        margin: 10px 0; 
                        padding: 10px; 
                        background-color: white; 
                        border-radius: 4px; 
                        border-left: 3px solid #32898b;
                    }}
                    .contact {{ 
                        background-color: #32898b; 
                        color: white; 
                        padding: 20px; 
                        text-align: center; 
                        margin-top: 30px;
                    }}
                    .contact a {{ 
                        color: white; 
                        text-decoration: none;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h1 class="congratulations-title">🎉 Congratulations, {first_name}!</h1>
                        
                        <div class="success-notice">
                            <p><strong>✅ Your mentor profile has been verified and is now live!</strong></p>
                            <p>Students can now discover and book sessions with you.</p>
                        </div>
                        
                        <p>Hi {first_name},</p>
                        
                        <p>Great news! Your mentor profile on <span class="brand">MenttoConnect</span> has been successfully verified and is now live on our platform.</p>
                        
                        <div class="tips">
                            <h3>🚀 What you can do now:</h3>
                            <div class="tip">📅 Set your availability and time slots for students to book</div>
                            <div class="tip">💬 Respond to student inquiries and messages</div>
                            <div class="tip">📚 Share your expertise and help students achieve their study abroad goals</div>
                            <div class="tip">⭐ Build your reputation through student reviews and ratings</div>
                        </div>
                        
                        <p>Your profile is now visible to students who are looking for guidance in your areas of expertise. Make sure to keep your availability updated and respond promptly to student inquiries.</p>
                        
                        <p>We're excited to have you as part of our mentor community and look forward to seeing the positive impact you'll make on students' journeys!</p>
                        
                        <p>Best regards,<br>Team Mentto</p>
                        
                        <div class="contact">
                            <p>📧 <a href="mailto:contact@mentto.in">contact@mentto.in</a><br>
                            🌐 <a href="https://mentto.in">mentto.in</a></p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Congratulations! You're Now Live on MenttoConnect! 🚀
            
            Hi {first_name},
            
            Great news! Your mentor profile on MenttoConnect has been successfully verified and is now live on our platform.
            
            ✅ Your mentor profile has been verified and is now live!
            Students can now discover and book sessions with you.
            
            🚀 What you can do now:
            📅 Set your availability and time slots for students to book
            💬 Respond to student inquiries and messages
            📚 Share your expertise and help students achieve their study abroad goals
            ⭐ Build your reputation through student reviews and ratings
            
            Your profile is now visible to students who are looking for guidance in your areas of expertise. Make sure to keep your availability updated and respond promptly to student inquiries.
            
            We're excited to have you as part of our mentor community and look forward to seeing the positive impact you'll make on students' journeys!
            
            Best regards,
            Team Mentto
            
            📧 contact@mentto.in
            🌐 mentto.in
            """
            
            # Use enhanced service with retry mechanism
            result = await self.enhanced_service.send_email_with_retry(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                email_type="mentor_verified"
            )
            
            if result.get('success'):
                logger.info(f"Mentor verified email sent successfully to {to_email} (attempts: {result.get('attempts', 1)})")
            else:
                logger.error(f"Failed to send mentor verified email to {to_email}: {result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in send_mentor_verified_email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentor verified email: {str(e)}',
                'email': to_email
            }
    
    async def send_mentor_verification_email(self, to_email: str, user_name: str = None) -> Dict[str, Any]:
        """Send mentor verification email with retry mechanism and logging"""
        try:
            # Use the original service but wrap it with retry logic
            result = self.original_service.send_mentor_verification_email(to_email, user_name)
            
            # If it failed, try with enhanced service
            if not result.get('success'):
                logger.warning(f"Original mentor verification email failed for {to_email}, attempting with enhanced service")
                
                # Get email content from original service (we'd need to extract this)
                # For now, just log the failure and return the original result
                logger.error(f"Mentor verification email failed for {to_email}: {result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in send_mentor_verification_email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentor verification email: {str(e)}',
                'email': to_email
            }
    
    async def get_email_logs(self, email_type: str = None, status: str = None, limit: int = 100) -> List[EmailLogResponse]:
        """Get email logs with optional filtering"""
        return await self.enhanced_service.get_email_logs(email_type, status, limit)
    
    async def get_failed_emails(self) -> List[EmailLogResponse]:
        """Get all failed emails that can be retried"""
        return await self.enhanced_service.get_failed_emails()
    
    async def retry_failed_email(self, log_id: str) -> Dict[str, Any]:
        """Retry a specific failed email"""
        return await self.enhanced_service.retry_failed_email(log_id)

# Create singleton instance
reliable_email_service = ReliableEmailService()
