"""
Email Service Startup Script
Initializes background email processing on application startup
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from app.services.email.background_email_service import background_email_service

logger = logging.getLogger(__name__)

@asynccontextmanager
async def email_service_lifespan():
    """Context manager for email service lifecycle"""
    try:
        # Start background email processor
        logger.info("Starting background email processor...")
        await background_email_service.start_background_processor()
        logger.info("Background email processor started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Error in email service startup: {e}")
        raise
    finally:
        # Stop background email processor
        logger.info("Stopping background email processor...")
        await background_email_service.stop_background_processor()
        logger.info("Background email processor stopped")

async def initialize_email_services():
    """Initialize all email services"""
    try:
        logger.info("Initializing email services...")
        
        # Start background email processor
        await background_email_service.start_background_processor()
        
        logger.info("Email services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing email services: {e}")
        raise

async def shutdown_email_services():
    """Shutdown all email services"""
    try:
        logger.info("Shutting down email services...")
        
        # Stop background email processor
        await background_email_service.stop_background_processor()
        
        logger.info("Email services shut down successfully")
        
    except Exception as e:
        logger.error(f"Error shutting down email services: {e}")
        raise
