"""
Main FastAPI application
"""
from fastapi import FastAPI, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.models.models import SuccessResponse, ErrorResponse
from app.services.email.background_email_service import background_email_service
from app.api.auth.routes import router as auth_router
from app.api.auth.firebase_auth import router as firebase_auth_router
from app.api.auth.mfa_routes import router as mfa_router
from app.api.user.routes import router as user_router
from app.api.mentee.routes import router as mentee_router
from app.api.mentor.routes import router as mentor_router
from app.api.chat.routes import router as chat_router
from app.api.calendar.routes import router as calendar_router
from app.api.admin.routes import router as admin_router
from app.api.mentorship.routes import router as mentorship_router
from app.api.review.routes import router as review_router
from app.api.conversation.routes import router as conversation_router
from app.api.session.routes import router as session_router
from app.api.questionnaire.routes import router as questionnaire_router
from app.api.payment.routes import router as payment_router
from app.api.payment.bank_details_routes import router as bank_details_router
from app.api.mentor.routes import router as mentor_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Mentto Backend API")
    # Start background email processor so queued emails are delivered
    try:
        await background_email_service.start_background_processor()
        logger.info("Background email processor started")
    except Exception as e:
        logger.error(f"Failed to start background email processor: {e}")
    yield
    logger.info("Shutting down Mentto Backend API")
    # Stop background email processor
    try:
        await background_email_service.stop_background_processor()
        logger.info("Background email processor stopped")
    except Exception as e:
        logger.error(f"Failed to stop background email processor: {e}")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Backend API for Mentto - Study Abroad Mentorship Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="Internal server error",
            error_code="INTERNAL_ERROR"
        ).dict()
    )

# Health check endpoint
@app.get("/health", response_model=SuccessResponse)
async def health_check():
    """Health check endpoint"""
    return SuccessResponse(message="Mentto Backend API is running")

# Include routers
app.include_router(auth_router)
app.include_router(firebase_auth_router)
app.include_router(mfa_router)
app.include_router(user_router)
app.include_router(mentee_router)
app.include_router(mentor_router)
app.include_router(chat_router)
app.include_router(calendar_router)
app.include_router(admin_router)
app.include_router(mentorship_router)
app.include_router(review_router)
app.include_router(conversation_router)
app.include_router(session_router)
app.include_router(questionnaire_router)
app.include_router(payment_router)
app.include_router(bank_details_router)
app.include_router(mentor_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
