"""
Conversation API routes for managing chat conversations
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query

from app.core.security.auth_dependencies import get_current_user, get_current_mentee_user, get_current_mentor_user
from app.models.models import ConversationSummary, ConversationMessage, UserResponse
from app.services.conversation.conversation_service import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/my-conversations", response_model=List[ConversationSummary])
async def get_my_conversations(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all conversations for the current user (mentee or mentor)"""
    try:
        if current_user.role == "mentee":
            conversations = await conversation_service.get_mentee_conversations(current_user.user_id)
        elif current_user.role == "mentor":
            conversations = await conversation_service.get_mentor_conversations(current_user.user_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role. Must be 'mentee' or 'mentor'"
            )
        
        return conversations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversations: {str(e)}"
        )

@router.get("/mentee", response_model=List[ConversationSummary])
async def get_mentee_conversations(
    current_user: UserResponse = Depends(get_current_mentee_user)
):
    """Get all conversations for the current mentee"""
    try:
        conversations = await conversation_service.get_mentee_conversations(current_user.user_id)
        return conversations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentee conversations: {str(e)}"
        )

@router.get("/mentor", response_model=List[ConversationSummary])
async def get_mentor_conversations(
    current_user: UserResponse = Depends(get_current_mentor_user)
):
    """Get all conversations for the current mentor"""
    try:
        conversations = await conversation_service.get_mentor_conversations(current_user.user_id)
        return conversations
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor conversations: {str(e)}"
        )

@router.get("/with/{other_user_id}/messages", response_model=List[ConversationMessage])
async def get_conversation_messages(
    other_user_id: str,
    limit: int = Query(50, ge=1, le=100, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get conversation messages between current user and another user"""
    try:
        messages = await conversation_service.get_conversation_messages(
            current_user.user_id, 
            other_user_id, 
            limit, 
            offset
        )
        return messages
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation messages: {str(e)}"
        )

@router.get("/recent", response_model=List[ConversationSummary])
async def get_recent_conversations(
    limit: int = Query(10, ge=1, le=50, description="Number of recent conversations to return"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get recent conversations for the current user"""
    try:
        if current_user.role == "mentee":
            conversations = await conversation_service.get_mentee_conversations(current_user.user_id)
        elif current_user.role == "mentor":
            conversations = await conversation_service.get_mentor_conversations(current_user.user_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role. Must be 'mentee' or 'mentor'"
            )
        
        # Return only the requested number of recent conversations
        return conversations[:limit]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent conversations: {str(e)}"
        )
