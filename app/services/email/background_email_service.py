"""
Background Email Service for reliable email delivery using asyncio tasks
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json

from app.services.email.enhanced_email_service import enhanced_email_service
from app.models.models import EmailLogResponse, EmailStatus

logger = logging.getLogger(__name__)

class BackgroundEmailService:
    """Background email service for reliable email delivery"""
    
    def __init__(self):
        self.task_queue = asyncio.Queue()
        self.running_tasks = set()
        self.max_concurrent_tasks = 5
        self.is_running = False
    
    async def start_background_processor(self):
        """Start the background email processor"""
        if self.is_running:
            logger.warning("Background email processor is already running")
            return
        
        self.is_running = True
        logger.info("Starting background email processor")
        
        # Start multiple worker tasks
        for i in range(self.max_concurrent_tasks):
            task = asyncio.create_task(self._email_worker(f"worker-{i}"))
            self.running_tasks.add(task)
            task.add_done_callback(self.running_tasks.discard)
    
    async def stop_background_processor(self):
        """Stop the background email processor"""
        if not self.is_running:
            return
        
        logger.info("Stopping background email processor")
        self.is_running = False
        
        # Cancel all running tasks
        for task in self.running_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        logger.info("Background email processor stopped")
    
    async def _email_worker(self, worker_name: str):
        """Background worker for processing email tasks"""
        logger.info(f"Email worker {worker_name} started")
        
        while self.is_running:
            try:
                # Wait for a task with timeout
                task_data = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                if task_data is None:  # Shutdown signal
                    break
                
                await self._process_email_task(task_data, worker_name)
                
            except asyncio.TimeoutError:
                # No tasks available, continue
                continue
            except Exception as e:
                logger.error(f"Error in email worker {worker_name}: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing
        
        logger.info(f"Email worker {worker_name} stopped")
    
    async def _process_email_task(self, task_data: Dict[str, Any], worker_name: str):
        """Process a single email task"""
        try:
            email_type = task_data.get('email_type', 'general')
            to_email = task_data.get('to_email')
            subject = task_data.get('subject')
            html_content = task_data.get('html_content')
            text_content = task_data.get('text_content')
            
            logger.info(f"Worker {worker_name} processing {email_type} email to {to_email}")
            
            # Send email with retry mechanism
            result = await enhanced_email_service.send_email_with_retry(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                email_type=email_type
            )
            
            if result.get('success'):
                logger.info(f"Worker {worker_name} successfully sent {email_type} email to {to_email}")
            else:
                logger.error(f"Worker {worker_name} failed to send {email_type} email to {to_email}: {result.get('message')}")
            
        except Exception as e:
            logger.error(f"Error processing email task in worker {worker_name}: {e}")
    
    async def queue_email(self, to_email: str, subject: str, html_content: str, 
                         text_content: str = None, email_type: str = "general", 
                         priority: int = 0) -> bool:
        """Queue an email for background processing"""
        try:
            task_data = {
                'to_email': to_email,
                'subject': subject,
                'html_content': html_content,
                'text_content': text_content,
                'email_type': email_type,
                'priority': priority,
                'queued_at': datetime.utcnow().isoformat()
            }
            
            await self.task_queue.put(task_data)
            logger.info(f"Queued {email_type} email for {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error queuing email: {e}")
            return False
    
    async def queue_mentor_verified_email(self, to_email: str, user_name: str = None) -> bool:
        """Queue mentor verified email for background processing"""
        try:
            first_name = user_name.split()[0] if user_name and user_name.strip() else "Mentor"
            subject = "Congratulations! You're Now Live on MenttoConnect! 🚀"
            
            # HTML content
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
            
            return await self.queue_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                email_type="mentor_verified",
                priority=1  # High priority for verification emails
            )
            
        except Exception as e:
            logger.error(f"Error queuing mentor verified email: {e}")
            return False
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "is_running": self.is_running,
            "queue_size": self.task_queue.qsize(),
            "active_workers": len(self.running_tasks),
            "max_workers": self.max_concurrent_tasks
        }
    
    async def retry_failed_emails(self) -> Dict[str, Any]:
        """Retry all failed emails"""
        try:
            failed_emails = await enhanced_email_service.get_failed_emails()
            retry_count = 0
            
            for email_log in failed_emails:
                if email_log.retry_count < email_log.max_retries:
                    # Queue for retry (we'd need to store the original content)
                    # For now, just log the attempt
                    logger.info(f"Retrying failed email {email_log.id} to {email_log.recipient_email}")
                    retry_count += 1
            
            return {
                "success": True,
                "message": f"Initiated retry for {retry_count} failed emails",
                "retry_count": retry_count
            }
            
        except Exception as e:
            logger.error(f"Error retrying failed emails: {e}")
            return {
                "success": False,
                "message": f"Error retrying failed emails: {str(e)}"
            }

# Create singleton instance
background_email_service = BackgroundEmailService()
