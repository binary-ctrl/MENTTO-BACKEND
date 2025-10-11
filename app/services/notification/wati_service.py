"""
WATI WhatsApp Service for sending WhatsApp notifications
"""

import logging
from typing import Optional, Dict, Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WATIService:
    """Lightweight client for WATI WhatsApp APIs."""

    def __init__(self) -> None:
        self.base_url = (settings.wati_base_url or "").rstrip("/")
        self.api_key = settings.wati_api_key
        self.enabled = bool(settings.enable_wati_notifications and self.base_url and self.api_key)

    def _auth_headers(self) -> Dict[str, str]:
        token = self.api_key or ""
        # Accept either raw token or already-prefixed 'Bearer ...'
        if token.lower().startswith("bearer "):
            auth_value = token
        else:
            auth_value = f"Bearer {token}"
        return {
            "Authorization": auth_value,
            "Content-Type": "application/json",
        }

    async def send_text_message(self, phone_number_e164: str, message: str) -> bool:
        """
        Send a simple WhatsApp text message using WATI.

        Expected WATI endpoint (may vary by account region/version):
        POST {base_url}/api/v1/sendSessionMessage
        Body: {"whatsappNumber": "+911234567890", "messageText": "..."}
        """
        if not self.enabled:
            logger.info("WATI not enabled or misconfigured; skipping WhatsApp send")
            return False

        url = f"{self.base_url}/api/v1/sendSessionMessage"
        payload = {
            "whatsappNumber": phone_number_e164,
            "messageText": message,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=self._auth_headers(), json=payload)
                if resp.status_code >= 200 and resp.status_code < 300:
                    logger.info("WATI message sent successfully")
                    return True
                logger.error(f"WATI send failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending WATI message: {e}")
            return False


wati_service = WATIService()


