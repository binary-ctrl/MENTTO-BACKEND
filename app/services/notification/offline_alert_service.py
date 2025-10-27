"""
Offline Alert Orchestrator

Sends WhatsApp (WATI) and Email notifications when a user receives a new
message but is offline.
"""

import logging
from typing import Optional, Dict, Any

from app.core.database import get_supabase
from app.core.config import settings
from app.models.models import ChatMessageResponse
from app.services.email import email_service
from app.services.notification.wati_service import wati_service
from app.utils.url_utils import format_auth_url

logger = logging.getLogger(__name__)


class OfflineAlertService:
    def __init__(self) -> None:
        self.supabase = get_supabase()

    async def _get_user_contact(self, user_id: str) -> Dict[str, Optional[str]]:
        """
        Fetch user email from `users` and try phone from mentee/mentor detail tables.
        """
        email: Optional[str] = None
        phone: Optional[str] = None

        try:
            # Primary email
            user_res = self.supabase.table("users").select("email, role").eq("user_id", user_id).execute()
            if user_res.data:
                email = user_res.data[0].get("email")
                role = user_res.data[0].get("role")
            else:
                role = None

            # Try mentee details
            mentee_res = self.supabase.table("mentee_details").select("phone_number").eq("user_id", user_id).execute()
            if mentee_res.data and mentee_res.data[0].get("phone_number"):
                phone = mentee_res.data[0]["phone_number"]

            # If not found, try mentor details
            if not phone:
                mentor_res = self.supabase.table("mentor_details").select("phone_number").eq("user_id", user_id).execute()
                if mentor_res.data and mentor_res.data[0].get("phone_number"):
                    phone = mentor_res.data[0]["phone_number"]

            return {"email": email, "phone": phone}
        except Exception as e:
            logger.error(f"Failed to fetch contact for {user_id}: {e}")
            return {"email": None, "phone": None}

    async def _get_mentorship_context(self, sender_id: str, recipient_id: str) -> Dict[str, Optional[str]]:
        """
        Get mentorship relationship context between sender and recipient.
        """
        try:
            # Check if there's an accepted mentorship relationship
            mentorship_res = self.supabase.table("mentorship_interest").select(
                "status, created_at, users!mentorship_interest_mentor_id_fkey(full_name, role), users!mentorship_interest_mentee_id_fkey(full_name, role)"
            ).or_(
                f"and(mentor_id.eq.{sender_id},mentee_id.eq.{recipient_id})",
                f"and(mentor_id.eq.{recipient_id},mentee_id.eq.{sender_id})"
            ).eq("status", "accepted").execute()

            if mentorship_res.data:
                relationship = mentorship_res.data[0]
                status = relationship.get("status")
                created_at = relationship.get("created_at")
                
                # Determine relationship type
                mentor_info = relationship.get("users!mentorship_interest_mentor_id_fkey", {})
                mentee_info = relationship.get("users!mentorship_interest_mentee_id_fkey", {})
                
                if mentor_info.get("user_id") == sender_id:
                    relationship_type = "mentor_to_mentee"
                    other_party_name = mentee_info.get("full_name", "Mentee")
                else:
                    relationship_type = "mentee_to_mentor"
                    other_party_name = mentor_info.get("full_name", "Mentor")
                
                return {
                    "has_relationship": True,
                    "relationship_type": relationship_type,
                    "other_party_name": other_party_name,
                    "status": status,
                    "created_at": created_at
                }
            else:
                return {
                    "has_relationship": False,
                    "relationship_type": None,
                    "other_party_name": None,
                    "status": None,
                    "created_at": None
                }
        except Exception as e:
            logger.error(f"Failed to fetch mentorship context: {e}")
            return {
                "has_relationship": False,
                "relationship_type": None,
                "other_party_name": None,
                "status": None,
                "created_at": None
            }

    def _format_whatsapp_message(self, message: ChatMessageResponse, context: Dict[str, Optional[str]] = None) -> str:
        sender = message.sender_name or "Someone"
        preview = message.content[:200]
        
        # Add ellipsis if message was truncated
        if len(message.content) > 200:
            preview += "..."
        
        # Add relationship context if available
        relationship_context = ""
        if context and context.get("has_relationship"):
            if context.get("relationship_type") == "mentor_to_mentee":
                relationship_context = "🎓 Your mentor"
            elif context.get("relationship_type") == "mentee_to_mentor":
                relationship_context = "👨‍🎓 Your mentee"
        
        return f"""🔔 *New Message on MenttoConnect*

👤 From: {sender}{f" ({relationship_context})" if relationship_context else ""}

💬 Message:
"{preview}"

📱 Reply now: Open your MenttoConnect app to continue the conversation.

---
*This is an automated notification. Please do not reply to this message.*"""

    def _format_email(self, message: ChatMessageResponse, context: Dict[str, Optional[str]] = None) -> Dict[str, str]:
        sender = message.sender_name or "Someone"
        preview = message.content[:300]
        
        # Add ellipsis if message was truncated
        if len(message.content) > 300:
            preview += "..."
        
        # Add relationship context if available
        relationship_context = ""
        if context and context.get("has_relationship"):
            if context.get("relationship_type") == "mentor_to_mentee":
                relationship_context = " (Your Mentor)"
            elif context.get("relationship_type") == "mentee_to_mentor":
                relationship_context = " (Your Mentee)"
        
        subject = f"🔔 New message from {sender}{relationship_context} on MenttoConnect"
        
        # Construct auth URL - ensure it works on both mobile and PC with proper protocol
        auth_url = format_auth_url()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Message - MenttoConnect</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background-color: white;
                    border-radius: 12px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #e9ecef;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #32898b;
                    margin-bottom: 10px;
                }}
                .message-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #32898b;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 8px;
                }}
                .sender {{
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 10px;
                }}
                .message-content {{
                    font-style: italic;
                    color: #6c757d;
                    white-space: pre-wrap;
                }}
                .cta-button {{
                    display: inline-block;
                    background-color: #32898b;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 20px 0;
                    text-align: center;
                }}
                .cta-button:hover {{
                    background-color: #2a7577;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #6c757d;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">🔔 MenttoConnect</div>
                    <p>You have a new message waiting for you</p>
                </div>
                
                <div class="message-box">
                    <div class="sender">👤 From: {sender}{f" {relationship_context}" if relationship_context else ""}</div>
                    <div class="message-content">"{preview}"</div>
                </div>
                
                <div style="text-align: center;">
                    <a href="{auth_url}" class="cta-button">💬 Open MenttoConnect to Reply</a>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification. Please do not reply to this email.</p>
                    <p>If you're having trouble accessing the link, copy and paste this URL into your browser:<br>
                    <a href="{auth_url}" style="color: #32898b;">{auth_url}</a></p>
                </div>
            </div>
        </body>
        </html>
        """.strip()
        
        text = f"""🔔 New Message on MenttoConnect

From: {sender}{relationship_context}

Message:
"{preview}"

Reply now: Open MenttoConnect to continue the conversation.
{auth_url}

---
This is an automated notification. Please do not reply to this email."""
        
        return {"subject": subject, "html": html, "text": text}

    async def maybe_notify_offline_recipient(self, message: ChatMessageResponse, is_recipient_online: bool) -> None:
        """
        If the recipient is offline, send WhatsApp (if enabled and phone present) and email.
        """
        if is_recipient_online:
            logger.info(f"Recipient {message.recipient_id} is online; skipping offline alerts")
            return

        contact = await self._get_user_contact(message.recipient_id)
        phone = contact.get("phone")
        email = contact.get("email")
        
        # Get mentorship context for better notification content
        context = await self._get_mentorship_context(message.sender_id, message.recipient_id)
        
        logger.info(
            f"Offline alerts for {message.recipient_id}: phone={'yes' if phone else 'no'}, email={'yes' if email else 'no'}, wati_enabled={settings.enable_wati_notifications}, relationship={context.get('relationship_type', 'none')}"
        )

        # WhatsApp via WATI (best-effort)
        if phone and settings.enable_wati_notifications:
            # Ensure E.164 formatting if possible; assume provided numbers are correct.
            whatsapp_text = self._format_whatsapp_message(message, context)
            try:
                sent = await wati_service.send_text_message(phone, whatsapp_text)
                logger.info(f"WATI send result for {message.recipient_id}: {sent}")
            except Exception as e:
                logger.error(f"Failed to send WhatsApp via WATI: {e}")

        # Email (best-effort)
        if email:
            formatted = self._format_email(message, context)
            try:
                email_sent = email_service.send_email(email, formatted["subject"], formatted["html"], formatted["text"])
                logger.info(f"Offline email send result for {message.recipient_id}: {email_sent}")
            except Exception as e:
                logger.error(f"Failed to send offline email: {e}")


offline_alert_service = OfflineAlertService()


