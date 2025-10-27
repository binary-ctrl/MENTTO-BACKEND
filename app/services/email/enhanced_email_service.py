"""
Enhanced Email Service with retry mechanism and comprehensive logging
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime, timedelta
import json
import time

from app.core.config import settings
from app.core.database import get_supabase
from app.models.models import EmailLogCreate, EmailStatus, EmailLogResponse

logger = logging.getLogger(__name__)

class EnhancedEmailService:
    """Enhanced email service with retry mechanism and comprehensive logging"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.from_email
        self.supabase = get_supabase()
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.retry_backoff = 2  # exponential backoff multiplier
    
    async def log_email_attempt(self, email_log: EmailLogCreate) -> str:
        """Log email attempt to database"""
        try:
            result = self.supabase.table("email_logs").insert({
                "recipient_email": email_log.recipient_email,
                "subject": email_log.subject,
                "email_type": email_log.email_type,
                "status": email_log.status.value,
                "error_message": email_log.error_message,
                "retry_count": email_log.retry_count,
                "max_retries": email_log.max_retries,
                "sent_at": email_log.sent_at.isoformat() if email_log.sent_at else None,
                "created_at": email_log.created_at.isoformat()
            }).execute()
            
            if result.data:
                return result.data[0]["id"]
            else:
                logger.error("Failed to create email log entry")
                return None
        except Exception as e:
            logger.error(f"Error logging email attempt: {e}")
            return None
    
    async def update_email_log(self, log_id: str, status: EmailStatus, error_message: str = None, sent_at: datetime = None):
        """Update email log status"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if error_message:
                update_data["error_message"] = error_message
            
            if sent_at:
                update_data["sent_at"] = sent_at.isoformat()
            
            self.supabase.table("email_logs").update(update_data).eq("id", log_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating email log: {e}")
    
    async def send_email_with_retry(self, to_email: str, subject: str, html_content: str, 
                                  text_content: str = None, email_type: str = "general") -> Dict[str, Any]:
        """Send email with retry mechanism and comprehensive logging"""
        
        # Create initial email log
        email_log = EmailLogCreate(
            recipient_email=to_email,
            subject=subject,
            email_type=email_type,
            status=EmailStatus.PENDING,
            max_retries=self.max_retries
        )
        
        log_id = await self.log_email_attempt(email_log)
        if not log_id:
            logger.error(f"Failed to create email log for {to_email}")
        
        # Attempt to send email with retries
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    # Wait before retry with exponential backoff
                    delay = self.retry_delay * (self.retry_backoff ** (attempt - 1))
                    logger.info(f"Retrying email to {to_email} in {delay} seconds (attempt {attempt + 1}/{self.max_retries + 1})")
                    await asyncio.sleep(delay)
                    
                    # Update log status to retrying
                    if log_id:
                        await self.update_email_log(log_id, EmailStatus.RETRYING, f"Retry attempt {attempt}")
                
                # Attempt to send email
                success = await self._send_email_sync(to_email, subject, html_content, text_content)
                
                if success:
                    # Update log as successful
                    if log_id:
                        await self.update_email_log(log_id, EmailStatus.SENT, sent_at=datetime.utcnow())
                    
                    logger.info(f"Email sent successfully to {to_email} on attempt {attempt + 1}")
                    return {
                        'success': True,
                        'message': 'Email sent successfully',
                        'email': to_email,
                        'attempts': attempt + 1,
                        'log_id': log_id
                    }
                else:
                    error_msg = f"SMTP send failed on attempt {attempt + 1}"
                    logger.warning(f"Email send failed to {to_email}: {error_msg}")
                    
                    if attempt == self.max_retries:
                        # Final failure
                        if log_id:
                            await self.update_email_log(log_id, EmailStatus.FAILED, 
                                                      f"Failed after {self.max_retries + 1} attempts: {error_msg}")
                        
                        return {
                            'success': False,
                            'message': f'Failed to send email after {self.max_retries + 1} attempts',
                            'email': to_email,
                            'attempts': attempt + 1,
                            'log_id': log_id
                        }
                    else:
                        # Update retry count
                        if log_id:
                            await self.update_email_log(log_id, EmailStatus.RETRYING, 
                                                      f"Retry {attempt + 1}/{self.max_retries}: {error_msg}")
                
            except Exception as e:
                error_msg = f"Exception on attempt {attempt + 1}: {str(e)}"
                logger.error(f"Email send exception to {to_email}: {error_msg}")
                
                if attempt == self.max_retries:
                    # Final failure
                    if log_id:
                        await self.update_email_log(log_id, EmailStatus.FAILED, error_msg)
                    
                    return {
                        'success': False,
                        'message': f'Email send failed after {self.max_retries + 1} attempts: {str(e)}',
                        'email': to_email,
                        'attempts': attempt + 1,
                        'log_id': log_id
                    }
                else:
                    # Update retry count
                    if log_id:
                        await self.update_email_log(log_id, EmailStatus.RETRYING, error_msg)
        
        # This should never be reached, but just in case
        return {
            'success': False,
            'message': 'Unexpected error in email retry logic',
            'email': to_email,
            'log_id': log_id
        }
    
    async def _send_email_sync(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Synchronous email sending (to be run in thread pool)"""
        try:
            if not all([self.smtp_server, self.smtp_username, self.smtp_password, self.from_email]):
                logger.error("Email configuration incomplete")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Create SMTP session
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    async def get_email_logs(self, email_type: str = None, status: str = None, limit: int = 100) -> List[EmailLogResponse]:
        """Get email logs with optional filtering"""
        try:
            query = self.supabase.table("email_logs").select("*")
            
            if email_type:
                query = query.eq("email_type", email_type)
            
            if status:
                query = query.eq("status", status)
            
            query = query.order("created_at", desc=True).limit(limit)
            result = query.execute()
            
            if result.data:
                return [EmailLogResponse(**log) for log in result.data]
            return []
            
        except Exception as e:
            logger.error(f"Error fetching email logs: {e}")
            return []
    
    async def get_failed_emails(self) -> List[EmailLogResponse]:
        """Get all failed emails that can be retried"""
        try:
            result = self.supabase.table("email_logs").select("*").eq("status", "failed").execute()
            
            if result.data:
                return [EmailLogResponse(**log) for log in result.data]
            return []
            
        except Exception as e:
            logger.error(f"Error fetching failed emails: {e}")
            return []
    
    async def retry_failed_email(self, log_id: str) -> Dict[str, Any]:
        """Retry a specific failed email"""
        try:
            # Get the email log
            result = self.supabase.table("email_logs").select("*").eq("id", log_id).execute()
            
            if not result.data:
                return {'success': False, 'message': 'Email log not found'}
            
            email_log = result.data[0]
            
            # Check if it can be retried
            if email_log['status'] != 'failed' or email_log['retry_count'] >= email_log['max_retries']:
                return {'success': False, 'message': 'Email cannot be retried'}
            
            # Retry the email (this would need the original content, which we'd need to store)
            # For now, just update the status
            await self.update_email_log(log_id, EmailStatus.PENDING, "Manual retry initiated")
            
            return {'success': True, 'message': 'Retry initiated'}
            
        except Exception as e:
            logger.error(f"Error retrying email {log_id}: {e}")
            return {'success': False, 'message': f'Error retrying email: {str(e)}'}

# Create singleton instance
enhanced_email_service = EnhancedEmailService()
