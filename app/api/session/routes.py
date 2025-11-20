"""
Session API routes for managing mentorship sessions
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
import logging

from app.core.security.auth_dependencies import get_current_user, get_current_mentee_user, get_current_mentor_user
from app.models.models import (
    SessionCreate, SessionUpdate, SessionResponse, SessionSummary, AllSessionsResponse,
    CallType, SessionStatus, UserResponse
)
from app.services.session.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

@router.post("/schedule", response_model=SessionResponse)
async def schedule_session(
    session_data: SessionCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Schedule a new mentorship session (mentee or mentor)"""
    try:
        session = await session_service.create_session(current_user.user_id, session_data, current_user.role)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )
        
        return session
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule session: {str(e)}"
        )

@router.get("/my-sessions", response_model=List[SessionResponse])
async def get_my_sessions(
    limit: int = Query(50, ge=1, le=100, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all sessions for the current user (mentee or mentor)"""
    try:
        if current_user.role == "mentee":
            sessions = await session_service.get_sessions_by_mentee(current_user.user_id, limit, offset)
        elif current_user.role == "mentor":
            sessions = await session_service.get_sessions_by_mentor(current_user.user_id, limit, offset)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role. Must be 'mentee' or 'mentor'"
            )
        
        return sessions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sessions: {str(e)}"
        )

@router.get("/mentee", response_model=List[SessionResponse])
async def get_mentee_sessions(
    limit: int = Query(50, ge=1, le=100, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Get all sessions for the current mentee"""
    try:
        sessions = await session_service.get_sessions_by_mentee(current_user.user_id, limit, offset)
        return sessions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentee sessions: {str(e)}"
        )

@router.get("/mentor", response_model=List[SessionResponse])
async def get_mentor_sessions(
    limit: int = Query(50, ge=1, le=100, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    current_user: UserResponse = Depends(get_current_mentor_user)
):
    """Get all sessions for the current mentor"""
    try:
        sessions = await session_service.get_sessions_by_mentor(current_user.user_id, limit, offset)
        return sessions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor sessions: {str(e)}"
        )

@router.get("/upcoming", response_model=List[SessionResponse])
async def get_upcoming_sessions(
    limit: int = Query(10, ge=1, le=50, description="Number of upcoming sessions to return"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get upcoming sessions for the current user"""
    try:
        sessions = await session_service.get_upcoming_sessions(current_user.user_id, current_user.role, limit)
        return sessions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upcoming sessions: {str(e)}"
        )

@router.get("/summary", response_model=SessionSummary)
async def get_session_summary(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get session summary for the current user"""
    try:
        summary = await session_service.get_session_summary(current_user.user_id, current_user.role)
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No sessions found"
            )
        
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session summary: {str(e)}"
        )

@router.get("/all-sessions", response_model=AllSessionsResponse)
async def get_all_sessions_divided(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all sessions divided into upcoming and past"""
    try:
        if current_user.role == "mentee" or current_user.role == "parent":
            all_sessions = await session_service.get_sessions_by_mentee(current_user.user_id, limit=1000, offset=0)
        elif current_user.role == "mentor":
            all_sessions = await session_service.get_sessions_by_mentor(current_user.user_id, limit=1000, offset=0)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role. Must be 'mentee', 'mentor' or 'parent'"
            )
        
        # Get current date and time for comparison
        from datetime import datetime
        now = datetime.now()
        
        logger.info(f"Current time: {now}")
        logger.info(f"Total sessions found: {len(all_sessions)}")
        
        upcoming_sessions = []
        past_sessions = []
        
        for session in all_sessions:
            # Filter out sessions where payment_status is "pending"
            # Only show sessions where payment has been completed (success or failed)
            if session.payment_status == "pending":
                logger.info(f"Skipping session {session.id} - payment_status is pending")
                continue
            
            # Parse session date and time
            session_date = datetime.strptime(session.scheduled_date, "%Y-%m-%d").date()
            
            # Handle both HH:MM and HH:MM:SS formats
            try:
                session_start_time = datetime.strptime(session.start_time, "%H:%M:%S").time()
            except ValueError:
                try:
                    session_start_time = datetime.strptime(session.start_time, "%H:%M").time()
                except ValueError:
                    # If both fail, skip this session
                    continue
            
            # Create datetime object for comparison (make both naive for comparison)
            session_datetime = datetime.combine(session_date, session_start_time)
            
            # Make both datetimes naive for comparison
            now_naive = now.replace(tzinfo=None) if now.tzinfo else now
            session_naive = session_datetime.replace(tzinfo=None) if session_datetime.tzinfo else session_datetime
            
            logger.info(f"Session: {session.scheduled_date} {session.start_time} -> {session_naive} vs {now_naive}")
            
            if session_naive > now_naive:
                upcoming_sessions.append(session)
                logger.info(f"Added to upcoming: {session.scheduled_date} {session.start_time}")
            else:
                past_sessions.append(session)
                logger.info(f"Added to past: {session.scheduled_date} {session.start_time}")
        
        # Sort upcoming sessions by date (earliest first)
        upcoming_sessions.sort(key=lambda x: (x.scheduled_date, x.start_time))
        
        # Sort past sessions by date (most recent first)
        past_sessions.sort(key=lambda x: (x.scheduled_date, x.start_time), reverse=True)
        
        return {
            "upcoming_sessions": upcoming_sessions,
            "past_sessions": past_sessions,
            "total_upcoming": len(upcoming_sessions),
            "total_past": len(past_sessions),
            "total_sessions": len(all_sessions)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get all sessions: {str(e)}"
        )

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific session by ID"""
    try:
        session = await session_service.get_session_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Verify user has access to this session
        if current_user.role == "mentee" and session.mentee_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        elif current_user.role == "mentor" and session.mentor_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )

@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an existing session"""
    try:
        session = await session_service.update_session(session_id, current_user.user_id, current_user.role, update_data)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or you don't have permission to update it"
            )
        
        return session
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a session"""
    try:
        success = await session_service.delete_session(session_id, current_user.user_id, current_user.role)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or you don't have permission to delete it"
            )
        
        return {"success": True, "message": "Session deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )

@router.get("/call-types", response_model=List[str])
async def get_call_types():
    """Get available call types"""
    return [call_type.value for call_type in CallType]

@router.get("/session-statuses", response_model=List[str])
async def get_session_statuses():
    """Get available session statuses"""
    return [status.value for status in SessionStatus]
