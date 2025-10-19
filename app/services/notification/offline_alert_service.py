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

    def _format_whatsapp_message(self, message: ChatMessageResponse) -> str:
        sender = message.sender_name or "Someone"
        preview = message.content[:200]
        return f"{sender} sent you a new message on MenttoConnect: \n\n{preview}\n\nOpen the app to reply."

    def _format_email(self, message: ChatMessageResponse) -> Dict[str, str]:
        sender = message.sender_name or "Someone"
        subject = f"New message from {sender} on MenttoConnect"
        preview = message.content[:300]
        # Construct auth URL - ensure it works on both mobile and PC
        auth_url = f"{settings.frontend_url}/auth" if not settings.frontend_url.endswith('/auth') else settings.frontend_url
        html = f"""
        <p>Hi,</p>
        <p><strong>{sender}</strong> sent you a new message on MenttoConnect.</p>
        <blockquote>{preview}</blockquote>
        <p><a href="{auth_url}">Open MenttoConnect</a> to reply.</p>
        """.strip()
        text = f"{sender} sent you a new message on MenttoConnect.\n\n{preview}\n\nOpen MenttoConnect to reply: {auth_url}"
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
        logger.info(
            f"Offline alerts for {message.recipient_id}: phone={'yes' if phone else 'no'}, email={'yes' if email else 'no'}, wati_enabled={settings.enable_wati_notifications}"
        )

        # WhatsApp via WATI (best-effort)
        if phone and settings.enable_wati_notifications:
            # Ensure E.164 formatting if possible; assume provided numbers are correct.
            whatsapp_text = self._format_whatsapp_message(message)
            try:
                sent = await wati_service.send_text_message(phone, whatsapp_text)
                logger.info(f"WATI send result for {message.recipient_id}: {sent}")
            except Exception as e:
                logger.error(f"Failed to send WhatsApp via WATI: {e}")

        # Email (best-effort)
        if email:
            formatted = self._format_email(message)
            try:
                email_sent = email_service.send_email(email, formatted["subject"], formatted["html"], formatted["text"])
                logger.info(f"Offline email send result for {message.recipient_id}: {email_sent}")
            except Exception as e:
                logger.error(f"Failed to send offline email: {e}")


offline_alert_service = OfflineAlertService()


