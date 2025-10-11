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
                        color: #2563eb; 
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
                        color: #2563eb; 
                        font-weight: bold; 
                    }}
                    .social {{ 
                        margin-top: 10px; 
                    }}
                    .social a {{ 
                        color: #2563eb; 
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
                        color: #2563eb;
                        text-align: center;
                    }}
                    .cta-button {{ 
                        display: inline-block; 
                        background-color: #2563eb; 
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
                        color: #2563eb; 
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
                        color: #2563eb; 
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
                            📧 <a href="mailto:contact@mentto.in" style="color: #2563eb;">contact@mentto.in</a></p>
                        </div>
                        
                        <p>We're thrilled to have you on board. Let's make your study journey clearer, smarter, and a lot less overwhelming together.</p>
                        
                        <p>Warmly,<br>Team Mentto</p>
                    </div>
                    <div class="footer">
                        <div class="brand">🌐 www.mentto.in</div>
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
            
            🌐 www.mentto.in
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
                        color: #059669;
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
                        color: #059669; 
                        font-weight: bold; 
                    }}
                    .contact {{ 
                        background-color: #f0fdf4; 
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
                            <p>📧 <a href="mailto:contact@mentto.in" style="color: #059669;">contact@mentto.in</a><br>
                            🌐 <a href="https://www.mentto.in" style="color: #059669;">www.mentto.in</a></p>
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
            🌐 www.mentto.in
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
            ward_display = f" for {ward_name}" if ward_name else ""
            
            subject = "Welcome to MenttoConnect – Supporting Your Child's Study Abroad Journey!"
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome to MenttoConnect - Parent</title>
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
                    .header {{ 
                        background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); 
                        color: white; 
                        padding: 30px; 
                        text-align: center;
                    }}
                    .content {{ 
                        padding: 40px 30px; 
                    }}
                    .welcome-title {{ 
                        font-size: 28px; 
                        margin: 0 0 10px 0; 
                        color: white;
                    }}
                    .welcome-subtitle {{ 
                        font-size: 16px; 
                        margin: 0; 
                        opacity: 0.9;
                    }}
                    .cta-button {{ 
                        display: inline-block; 
                        background-color: #7c3aed; 
                        color: white; 
                        padding: 15px 30px; 
                        text-decoration: none; 
                        border-radius: 6px; 
                        font-weight: bold; 
                        margin: 20px 0; 
                    }}
                    .steps {{ 
                        background-color: #faf5ff; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
                        border-left: 4px solid #7c3aed;
                    }}
                    .step {{ 
                        margin: 15px 0; 
                        padding-left: 25px; 
                        position: relative;
                    }}
                    .step::before {{ 
                        content: "✓"; 
                        position: absolute; 
                        left: 0; 
                        color: #7c3aed; 
                        font-weight: bold;
                    }}
                    .support {{ 
                        background-color: #f8fafc; 
                        padding: 20px; 
                        border-radius: 6px; 
                        margin: 20px 0; 
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
                        color: #7c3aed; 
                        font-weight: bold; 
                    }}
                    .social {{ 
                        margin-top: 10px; 
                    }}
                    .social a {{ 
                        color: #7c3aed; 
                        text-decoration: none; 
                        margin: 0 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="welcome-title">Welcome, Parent!</h1>
                        <p class="welcome-subtitle">Supporting your child's study abroad dreams</p>
                    </div>
                    <div class="content">
                        <h2>Hi {first_name},</h2>
                        <p>Welcome to <span class="brand">MenttoConnect</span>! We understand that supporting your child's study abroad journey{ward_display} is both exciting and challenging. We're here to help make this process smoother and more informed for your family.</p>
                        
                        <div class="steps">
                            <h3>🏠 How MenttoConnect Helps Parents</h3>
                            <div class="step">Complete your parent profile to share your child's study abroad goals</div>
                            <div class="step">Connect with experienced mentors who understand your concerns</div>
                            <div class="step">Get guidance on financial planning and scholarship opportunities</div>
                            <div class="step">Stay informed about application deadlines and requirements</div>
                            <div class="step">Access resources to support your child's preparation</div>
                        </div>
                        
                        <div class="support">
                            <h3>💝 What We Offer Parents</h3>
                            <ul>
                                <li>🎓 Expert guidance on university and course selection</li>
                                <li>💰 Financial planning and scholarship information</li>
                                <li>📋 Application process support and timeline management</li>
                                <li>🌍 Country-specific insights and safety information</li>
                                <li>🤝 Direct communication with experienced mentors</li>
                                <li>📚 Resources to help prepare your child for study abroad</li>
                            </ul>
                        </div>
                        
                        <p>As a parent, you play a crucial role in your child's study abroad journey. Our platform provides you with:</p>
                        <ul>
                            <li>📊 Transparent information about costs and requirements</li>
                            <li>🎯 Personalized mentor matching based on your child's goals</li>
                            <li>📞 Direct access to mentors for your questions and concerns</li>
                            <li>📅 Timeline guidance to keep applications on track</li>
                            <li>🔒 Safe and secure platform for all communications</li>
                        </ul>
                        
                        <p>We believe that informed parents make confident decisions. Let us help you support your child's dreams while ensuring you have all the information you need.</p>
                        
                        <p>Ready to get started? Complete your parent profile and connect with mentors who can guide your family through this important journey.</p>
                        
                        <p>If you have any questions or concerns, our support team is always available to help.</p>
                        
                        <p>Best regards,<br>Team MenttoConnect</p>
                    </div>
                    <div class="footer">
                        <div class="brand">mentto.in</div>
                        <div class="social">
                            <a href="https://instagram.com/mentto.official" target="_blank">Instagram</a>
                            <a href="mailto:support@mentto.in" target="_blank">Email Support</a>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text content
            text_content = f"""
            Welcome to MenttoConnect, {first_name}!
            
            Welcome to MenttoConnect! We understand that supporting your child's study abroad journey{ward_display} is both exciting and challenging. We're here to help make this process smoother and more informed for your family.
            
            How MenttoConnect Helps Parents:
            ✓ Complete your parent profile to share your child's study abroad goals
            ✓ Connect with experienced mentors who understand your concerns
            ✓ Get guidance on financial planning and scholarship opportunities
            ✓ Stay informed about application deadlines and requirements
            ✓ Access resources to support your child's preparation
            
            What We Offer Parents:
            🎓 Expert guidance on university and course selection
            💰 Financial planning and scholarship information
            📋 Application process support and timeline management
            🌍 Country-specific insights and safety information
            🤝 Direct communication with experienced mentors
            📚 Resources to help prepare your child for study abroad
            
            As a parent, you play a crucial role in your child's study abroad journey. Our platform provides you with:
            📊 Transparent information about costs and requirements
            🎯 Personalized mentor matching based on your child's goals
            📞 Direct access to mentors for your questions and concerns
            📅 Timeline guidance to keep applications on track
            🔒 Safe and secure platform for all communications
            
            We believe that informed parents make confident decisions. Let us help you support your child's dreams while ensuring you have all the information you need.
            
            Ready to get started? Complete your parent profile and connect with mentors who can guide your family through this important journey.
            
            If you have any questions or concerns, our support team is always available to help.
            
            Best regards,
            Team MenttoConnect
            
            mentto.in | @mentto.official | support@mentto.in
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
