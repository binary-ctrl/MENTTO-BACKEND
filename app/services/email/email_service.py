"""
Email Service for sending OTP and other emails
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import random
import string
from datetime import datetime, timedelta
import json

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails including OTP verification"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.from_email
        
        # Store OTPs temporarily (in production, use Redis or database)
        self.otp_storage = {}
        self.redis_client = None
        
        # Try to initialize Redis if available
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if available"""
        try:
            import redis
            redis_url = getattr(settings, 'redis_url', None)
            if redis_url:
                self.redis_client = redis.from_url(redis_url)
                logger.info("Redis client initialized for OTP storage")
            else:
                logger.info("Redis not configured, using in-memory storage")
        except ImportError:
            logger.info("Redis not available, using in-memory storage")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}, using in-memory storage")
    
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP"""
        return ''.join(random.choices(string.digits, k=length))
    
    def store_otp(self, email: str, otp: str, expiry_minutes: int = 10) -> None:
        """Store OTP with expiry time"""
        expiry_time = datetime.now() + timedelta(minutes=expiry_minutes)
        otp_data = {
            'otp': otp,
            'expires_at': expiry_time.isoformat(),
            'attempts': 0
        }
        
        if self.redis_client:
            # Store in Redis with TTL
            key = f"otp:{email}"
            self.redis_client.setex(key, expiry_minutes * 60, json.dumps(otp_data))
        else:
            # Store in memory
            self.otp_storage[email] = otp_data
    
    def verify_otp(self, email: str, provided_otp: str) -> bool:
        """Verify OTP and handle attempts"""
        # Get OTP data
        if self.redis_client:
            key = f"otp:{email}"
            otp_json = self.redis_client.get(key)
            if not otp_json:
                return False
            otp_data = json.loads(otp_json)
        else:
            if email not in self.otp_storage:
                return False
            otp_data = self.otp_storage[email]
        
        # Check if OTP has expired
        expires_at = datetime.fromisoformat(otp_data['expires_at'])
        if datetime.now() > expires_at:
            self._delete_otp(email)
            return False
        
        # Check attempt limit (max 3 attempts)
        if otp_data['attempts'] >= 3:
            self._delete_otp(email)
            return False
        
        # Increment attempts
        otp_data['attempts'] += 1
        
        # Update attempts count
        if self.redis_client:
            key = f"otp:{email}"
            self.redis_client.setex(key, 600, json.dumps(otp_data))  # 10 minutes TTL
        else:
            self.otp_storage[email] = otp_data
        
        # Verify OTP
        if otp_data['otp'] == provided_otp:
            self._delete_otp(email)
            return True
        
        return False
    
    def _delete_otp(self, email: str) -> None:
        """Delete OTP from storage"""
        if self.redis_client:
            key = f"otp:{email}"
            self.redis_client.delete(key)
        else:
            if email in self.otp_storage:
                del self.otp_storage[email]
    
    def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email using SMTP"""
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
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_otp_email(self, to_email: str, user_name: str = None) -> dict:
        """Send OTP verification email"""
        try:
            # Generate OTP
            otp = self.generate_otp()
            
            # Store OTP
            self.store_otp(to_email, otp)
            
            # Create email content
            subject = "Complete Your Registration – MenttoConnect"
            
            # Extract first name from user_name if available
            first_name = user_name.split()[0] if user_name and user_name.strip() else "there"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Complete Your Registration – MenttoConnect</title>
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
                    .otp-code {{ 
                        font-size: 24px; 
                        font-weight: bold; 
                        color: #32898b; 
                        text-align: center; 
                        margin: 20px 0; 
                        padding: 15px; 
                        background-color: #f8fafc; 
                        border: 2px solid #e2e8f0; 
                        border-radius: 6px; 
                        letter-spacing: 2px; 
                        font-family: 'Courier New', monospace;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .social {{ 
                        margin-top: 10px; 
                    }}
                    .social a {{ 
                        color: #32898b; 
                        text-decoration: none; 
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h2>Hi {first_name},</h2>
                        <p>We received a request to register a new account on <span class="brand">MenttoConnect</span>. To complete your registration, please verify your email using the one-time password (OTP) below:</p>
                        
                        <div class="otp-code">OTP: {otp}</div>
                        
                        <p>Enter this code on the platform to confirm your email address.</p>
                        
                        <p><em>If you did not initiate this request, please ignore this email.</em></p>
                        
                        <p>Regards,<br>Team Mentto</p>
                    </div>
                    <div class="footer">
                        <div class="brand">mentto.in</div>
                        <div class="social">
                            <a href="https://instagram.com/mentto.official" target="_blank">@mentto.official</a>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Hi {first_name},
            
            We received a request to register a new account on MenttoConnect. To complete your registration, please verify your email using the one-time password (OTP) below:
            
            OTP: {otp}
            
            Enter this code on the platform to confirm your email address.
            
            If you did not initiate this request, please ignore this email.
            
            Regards,
            Team Mentto
            mentto.in | @mentto.official
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                return {
                    'success': True,
                    'message': 'OTP sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send OTP email'
                }
                
        except Exception as e:
            logger.error(f"Error sending OTP email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending OTP email: {str(e)}'
            }

    def send_mentee_onboarding_email(self, to_email: str, user_name: str = None) -> dict:
        """Send onboarding email to new mentee"""
        try:
            # Extract first name from user_name if available
            first_name = user_name.split()[0] if user_name and user_name.strip() else "Student"
            
            subject = "Welcome to MenttoConnect!"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome to MenttoConnect</title>
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
                    .welcome-title {{ 
                        font-size: 28px; 
                        margin: 0 0 20px 0; 
                        color: #32898b;
                        text-align: center;
                    }}
                    .cta-button {{ 
                        display: inline-block; 
                        background-color: #32898b; 
                        color: white; 
                        padding: 15px 30px; 
                        text-decoration: none; 
                        border-radius: 6px; 
                        font-weight: bold; 
                        margin: 20px 0; 
                    }}
                    .steps {{ 
                        background-color: #f8fafc; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                    }}
                    .step {{ 
                        margin: 15px 0; 
                        padding-left: 25px; 
                        position: relative;
                    }}
                    .step::before {{ 
                        content: "✅"; 
                        position: absolute; 
                        left: 0; 
                        color: #32898b; 
                        font-weight: bold;
                    }}
                    .pro-tip {{ 
                        background-color: #fef3c7; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #f59e0b;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .contact {{ 
                        background-color: #f0f9ff; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h1 class="welcome-title">Welcome to MenttoConnect!</h1>
                        
                        <p>Hi {first_name},</p>
                        
                        <p>Welcome to <span class="brand">MenttoConnect</span>! We're so excited to be a part of your study journey!</p>
                        
                        <p>You've just unlocked access to Alumni who've been there, done that – they've faced the same questions and challenges you're dealing with, and they're here to share real, honest advice.</p>
                        
                        <p>Whether you're confused between courses, working on your SOP, or trying to understand what career options look like, your mentors are here to simplify things and support you every step of the way.</p>
                        
                        <div class="steps">
                            <h3>Here's how to get started:</h3>
                            <div class="step">Browse through verified mentor profiles</div>
                            <div class="step">Book a 1:1 session with someone who aligns with your goals</div>
                            <div class="step">Keep all conversations on MenttoConnect</div>
                            <div class="step">Leave a review after your session, it helps future students like you!</div>
                        </div>
                        
                        <div class="pro-tip">
                            <strong>💡 Pro Tip:</strong> The more specific your questions, the more value you'll get.
                        </div>
                        
                        <div class="contact">
                            <p>If you need anything, just reach out:<br>
                            📧 <a href="mailto:contact@mentto.in" style="color: white;">contact@mentto.in</a></p>
                        </div>
                        
                        <p>We're thrilled to have you on board. Let's make your study journey clearer, smarter, and a lot less overwhelming together.</p>
                        
                        <p>Warmly,<br>Team Mentto</p>
                    </div>
                    <div class="footer">
                        <div class="brand">🌐 mentto.in</div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Welcome to MenttoConnect!
            
            Hi {first_name},
            
            Welcome to MenttoConnect! We're so excited to be a part of your study journey!
            
            You've just unlocked access to Alumni who've been there, done that – they've faced the same questions and challenges you're dealing with, and they're here to share real, honest advice.
            
            Whether you're confused between courses, working on your SOP, or trying to understand what career options look like, your mentors are here to simplify things and support you every step of the way.
            
            Here's how to get started:
            ✅ Browse through verified mentor profiles
            ✅ Book a 1:1 session with someone who aligns with your goals
            ✅ Keep all conversations on MenttoConnect
            ✅ Leave a review after your session, it helps future students like you!
            
            💡 Pro Tip: The more specific your questions, the more value you'll get.
            
            If you need anything, just reach out:
            📧 contact@mentto.in
            
            We're thrilled to have you on board. Let's make your study journey clearer, smarter, and a lot less overwhelming together.
            
            Warmly,
            Team Mentto
            
            🌐 mentto.in
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Mentee onboarding email sent successfully to {to_email}")
                return {
                    'success': True,
                    'message': 'Mentee onboarding email sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send mentee onboarding email'
                }
                
        except Exception as e:
            logger.error(f"Error sending mentee onboarding email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentee onboarding email: {str(e)}'
            }

    def send_mentor_onboarding_email(self, to_email: str, user_name: str = None) -> dict:
        """Send onboarding email to new mentor"""
        try:
            # Extract first name from user_name if available
            first_name = user_name.split()[0] if user_name and user_name.strip() else "Mentor"
            
            subject = "Welcome to MenttoConnect"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome to MenttoConnect - Mentor</title>
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
                    .welcome-title {{ 
                        font-size: 28px; 
                        margin: 0 0 20px 0; 
                        color: #32898b;
                        text-align: center;
                    }}
                    .review-notice {{ 
                        background-color: #fef3c7; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #f59e0b;
                        text-align: center;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .contact {{ 
                        background-color: #32898b; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        text-align: center;
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h1 class="welcome-title">Welcome to MenttoConnect</h1>
                        
                        <p>Hi {first_name},</p>
                        
                        <p>Welcome to <span class="brand">MenttoConnect</span>! We're thrilled to have you on board as a mentor and can't wait for students to benefit from your experience.</p>
                        
                        <div class="review-notice">
                            <p><strong>📋 Your profile is currently under review.</strong> We'll notify you as soon as it's verified. This usually takes 3–4 business days, so hang tight!</p>
                        </div>
                        
                        <div class="contact">
                            <p>In the meantime, feel free to reach out if you have any questions. We're always here to help.</p>
                        </div>
                        
                        <p>Warmly,<br>Team Mentto</p>
                        
                        <div class="contact">
                            <p>                            📧 <a href="mailto:contact@mentto.in" style="color: white;">contact@mentto.in</a><br>
                            🌐 <a href="https://mentto.in" style="color: white;">mentto.in</a></p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Welcome to MenttoConnect
            
            Hi {first_name},
            
            Welcome to MenttoConnect! We're thrilled to have you on board as a mentor and can't wait for students to benefit from your experience.
            
            Your profile is currently under review. We'll notify you as soon as it's verified. This usually takes 3–4 business days, so hang tight!
            
            In the meantime, feel free to reach out if you have any questions. We're always here to help.
            
            Warmly,
            Team Mentto
            📧 contact@mentto.in
            🌐 mentto.in
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Mentor onboarding email sent successfully to {to_email}")
                return {
                    'success': True,
                    'message': 'Mentor onboarding email sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send mentor onboarding email'
                }
                
        except Exception as e:
            logger.error(f"Error sending mentor onboarding email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentor onboarding email: {str(e)}'
            }

    def send_parent_onboarding_email(self, to_email: str, user_name: str = None, ward_name: str = None) -> dict:
        """Send onboarding email to new parent"""
        try:
            # Extract first name from user_name if available
            first_name = user_name.split()[0] if user_name and user_name.strip() else "there"
            
            subject = "Welcome to MenttoConnect!"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome to MenttoConnect</title>
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
                    .welcome-title {{ 
                        font-size: 28px; 
                        margin: 0 0 20px 0; 
                        color: #32898b;
                        text-align: center;
                    }}
                    .steps {{ 
                        background-color: #f8fafc; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                    }}
                    .step {{ 
                        margin: 15px 0; 
                        padding-left: 25px; 
                        position: relative;
                    }}
                    .step::before {{ 
                        content: "✅"; 
                        position: absolute; 
                        left: 0; 
                        color: #32898b; 
                        font-weight: bold;
                    }}
                    .pro-tip {{ 
                        background-color: #fef3c7; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #f59e0b;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .contact {{ 
                        background-color: #f0f9ff; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h1 class="welcome-title">Welcome to MenttoConnect!</h1>
                        
                        <p>Hi {first_name},</p>
                        
                        <p>Welcome to <span class="brand">MenttoConnect</span>! We're so excited to have you on board.</p>
                        
                        <p>You've just unlocked access to verified Alumni Mentors who've been there, done that – they've faced the same questions and challenges your child might be navigating right now, and they're here to share real, honest advice with you.</p>
                        
                        <p>Whether you're exploring the right courses, universities, visa options, or career paths for your ward, our mentors are here to make the process simpler and more transparent – so you can guide your child with confidence.</p>
                        
                        <div class="steps">
                            <h3>Here's how to get started:</h3>
                            <div class="step">Browse through verified mentor profiles</div>
                            <div class="step">Book a 1:1 session with a mentor who aligns with your goals</div>
                            <div class="step">Keep all conversations safely within MenttoConnect</div>
                            <div class="step">Leave a review after your session – it helps other parents and students like you!</div>
                        </div>
                        
                        <div class="pro-tip">
                            <strong>💡 Pro Tip:</strong> The more specific your questions, the more value you'll get from each session.
                        </div>
                        
                        <div class="contact">
                            <p>If you need anything, just reach out:<br>
                            📧 <a href="mailto:contact@mentto.in" style="color: white;">contact@mentto.in</a></p>
                        </div>
                        
                        <p>We're thrilled to have you as part of the Mentto community – together, let's make your child's career journey clearer, smarter, and stress-free.</p>
                        
                        <p>Warmly,<br>Team Mentto</p>
                    </div>
                    <div class="footer">
                        <div class="brand">🌐 mentto.in</div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Welcome to MenttoConnect!
            
            Hi {first_name},
            
            Welcome to MenttoConnect! We're so excited to have you on board.
            
            You've just unlocked access to verified Alumni Mentors who've been there, done that – they've faced the same questions and challenges your child might be navigating right now, and they're here to share real, honest advice with you.
            
            Whether you're exploring the right courses, universities, visa options, or career paths for your ward, our mentors are here to make the process simpler and more transparent – so you can guide your child with confidence.
            
            Here's how to get started:
            ✅ Browse through verified mentor profiles
            ✅ Book a 1:1 session with a mentor who aligns with your goals
            ✅ Keep all conversations safely within MenttoConnect
            ✅ Leave a review after your session – it helps other parents and students like you!
            
            💡 Pro Tip: The more specific your questions, the more value you'll get from each session.
            
            If you need anything, just reach out:
            📧 contact@mentto.in
            
            We're thrilled to have you as part of the Mentto community – together, let's make your child's career journey clearer, smarter, and stress-free.
            
            Warmly,
            Team Mentto
            
            🌐 mentto.in
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Parent onboarding email sent successfully to {to_email}")
                return {
                    'success': True,
                    'message': 'Parent onboarding email sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send parent onboarding email'
                }
                
        except Exception as e:
            logger.error(f"Error sending parent onboarding email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending parent onboarding email: {str(e)}'
            }

    def send_mentor_verification_email(self, to_email: str, user_name: str = None) -> dict:
        """Send email notification to mentor that their profile is under verification"""
        try:
            # Extract first name from user_name if available
            first_name = user_name.split()[0] if user_name and user_name.strip() else "Mentor"
            
            subject = "Your Profile is Under Verification - MenttoConnect"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Profile Under Verification - MenttoConnect</title>
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
                    .verification-title {{ 
                        font-size: 28px; 
                        margin: 0 0 20px 0; 
                        color: #32898b;
                        text-align: center;
                    }}
                    .verification-notice {{ 
                        background-color: #fef3c7; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #f59e0b;
                        text-align: center;
                    }}
                    .steps {{ 
                        background-color: #f8fafc; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                    }}
                    .step {{ 
                        margin: 15px 0; 
                        padding-left: 25px; 
                        position: relative;
                    }}
                    .step::before {{ 
                        content: "⏳"; 
                        position: absolute; 
                        left: 0; 
                        color: #32898b; 
                        font-weight: bold;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .contact {{ 
                        background-color: #32898b; 
                        padding: 15px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        text-align: center;
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h1 class="verification-title">Profile Under Verification</h1>
                        
                        <p>Hi {first_name},</p>
                        
                        <p>Thank you for completing your mentor profile on <span class="brand">MenttoConnect</span>! We've received all your information and your profile is now under verification.</p>
                        
                        <div class="verification-notice">
                            <p><strong>📋 Your profile is currently under review.</strong> Our team will carefully review your application and verify your credentials. This process usually takes 3–4 business days.</p>
                        </div>
                        
                        <div class="steps">
                            <h3>What happens next?</h3>
                            <div class="step">Our team reviews your educational background and experience</div>
                            <div class="step">We verify your university credentials and work experience</div>
                            <div class="step">You'll receive an email notification once verification is complete</div>
                            <div class="step">Once verified, students can start booking sessions with you</div>
                        </div>
                        
                        <div class="contact">
                            <p>If you have any questions during this process, feel free to reach out to us. We're here to help!</p>
                        </div>
                        
                        <p>We appreciate your patience and look forward to having you as part of our mentor community.</p>
                        
                        <p>Best regards,<br>Team Mentto</p>
                        
                        <div class="contact">
                            <p>                            📧 <a href="mailto:contact@mentto.in" style="color: white;">contact@mentto.in</a><br>
                            🌐 <a href="https://mentto.in" style="color: white;">mentto.in</a></p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Profile Under Verification - MenttoConnect
            
            Hi {first_name},
            
            Thank you for completing your mentor profile on MenttoConnect! We've received all your information and your profile is now under verification.
            
            Your profile is currently under review. Our team will carefully review your application and verify your credentials. This process usually takes 3–4 business days.
            
            What happens next?
            ⏳ Our team reviews your educational background and experience
            ⏳ We verify your university credentials and work experience
            ⏳ You'll receive an email notification once verification is complete
            ⏳ Once verified, students can start booking sessions with you
            
            If you have any questions during this process, feel free to reach out to us. We're here to help!
            
            We appreciate your patience and look forward to having you as part of our mentor community.
            
            Best regards,
            Team Mentto
            
            📧 contact@mentto.in
            🌐 mentto.in
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Mentor verification email sent successfully to {to_email}")
                return {
                    'success': True,
                    'message': 'Mentor verification email sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send mentor verification email'
                }
                
        except Exception as e:
            logger.error(f"Error sending mentor verification email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentor verification email: {str(e)}'
            }

    def send_mentor_verified_email(self, to_email: str, user_name: str = None) -> dict:
        """Send email notification to mentor that their profile has been verified"""
        try:
            # Extract first name from user_name if available
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
                        border: 1px solid #e2e8f0;
                    }}
                    .tip-item {{ 
                        margin: 10px 0; 
                        padding: 8px 0;
                    }}
                    .footer {{ 
                        text-align: center; 
                        margin-top: 30px; 
                        color: #666; 
                        font-size: 14px; 
                        border-top: 1px solid #e2e8f0;
                        padding-top: 20px;
                    }}
                    .brand {{ 
                        color: #32898b; 
                        font-weight: bold; 
                    }}
                    .emoji {{ 
                        font-size: 1.2em; 
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h2 class="congratulations-title">Congratulations! You're Now Live on MenttoConnect! 🚀</h2>
                        
                        <p>Hi {first_name},</p>
                        
                        <div class="success-notice">
                            <strong>🎉 Your profile has been approved and is now live on MenttoConnect!</strong>
                        </div>
                        
                        <p>Thank you for offering your time and experience to guide students on their study abroad journey. We're so excited to have you on board.</p>
                        
                        <p>Here's everything you need to know to get started:</p>
                        
                        <div class="tips">
                            <div class="tip-item"><span class="emoji">🔗</span> Keep your calendar link updated so mentees can easily book sessions with you.</div>
                            <div class="tip-item"><span class="emoji">📣</span> Feel free to share your MenttoConnect profile on LinkedIn or with anyone who reaches out directly. The more visibility, the better!</div>
                            <div class="tip-item"><span class="emoji">🗨️</span> Kindly keep all conversations within the MenttoConnect platform for a smoother and safer experience.</div>
                            <div class="tip-item"><span class="emoji">⭐</span> Encourage mentees to leave a review after their session. It helps build your credibility and trust with future students.</div>
                        </div>
                        
                        <p>Need help? Have questions? We're just a message away.<br>
                        📧 <a href="mailto:contact@mentto.in">contact@mentto.in</a></p>
                        
                        <p>At Mentto, our mission is to ensure you're rewarded for your time and knowledge, while students receive real, honest, and practical guidance from someone who's truly been there, done that.</p>
                        
                        <p>Thanks again for being part of the Mentto. Your mentorship truly makes a difference. 💛</p>
                        
                        <p>Warm regards,<br>Team Mentto</p>
                        
                        <div class="footer">
                            <p>🌐 <a href="https://mentto.in" class="brand">mentto.in</a></p>
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
            
            Congratulations! Your profile has been approved and is now live on MenttoConnect! 
            
            Thank you for offering your time and experience to guide students on their study abroad journey. We're so excited to have you on board.
            
            Here's everything you need to know to get started:
            
            🔗 Keep your calendar link updated so mentees can easily book sessions with you.
            📣 Feel free to share your MenttoConnect profile on LinkedIn or with anyone who reaches out directly. The more visibility, the better!
            🗨️ Kindly keep all conversations within the MenttoConnect platform for a smoother and safer experience.
            ⭐ Encourage mentees to leave a review after their session. It helps build your credibility and trust with future students.
            
            Need help? Have questions? We're just a message away.
            📧 contact@mentto.in
            
            At Mentto, our mission is to ensure you're rewarded for your time and knowledge, while students receive real, honest, and practical guidance from someone who's truly been there, done that.
            
            Thanks again for being part of the Mentto. Your mentorship truly makes a difference. 💛
            
            Warm regards,
            Team Mentto
            🌐 mentto.in
            """
            
            # Send email
            success = self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Mentor verified email sent successfully to {to_email}")
                return {
                    'success': True,
                    'message': 'Mentor verified email sent successfully',
                    'email': to_email
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send mentor verified email'
                }
                
        except Exception as e:
            logger.error(f"Error sending mentor verified email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending mentor verified email: {str(e)}'
            }

    def send_onboarding_email(self, to_email: str, user_role: str, user_name: str = None, ward_name: str = None) -> dict:
        """Send appropriate onboarding email based on user role"""
        try:
            if user_role.lower() == "mentee":
                return self.send_mentee_onboarding_email(to_email, user_name)
            elif user_role.lower() == "mentor":
                return self.send_mentor_onboarding_email(to_email, user_name)
            elif user_role.lower() == "parent":
                return self.send_parent_onboarding_email(to_email, user_name, ward_name)
            else:
                logger.warning(f"Unknown user role for onboarding email: {user_role}")
                return {
                    'success': False,
                    'message': f'Unknown user role: {user_role}'
                }
        except Exception as e:
            logger.error(f"Error sending onboarding email: {str(e)}")
            return {
                'success': False,
                'message': f'Error sending onboarding email: {str(e)}'
            }

# Create a singleton instance
email_service = EmailService()
