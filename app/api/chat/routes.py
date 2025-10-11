"""
Firebase Chat API routes for 1:1 messaging
"""

from fastapi import APIRouter, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from typing import List, Optional
import logging
import json

from app.core.security.auth_dependencies import get_current_user
from app.models.models import (
    TokenData,
    ChatMessageCreate, 
    ChatMessageResponse, 
    ChatConversationResponse,
    SuccessResponse
)
from app.services.chat.firebase_chat_service import firebase_chat_service
from app.services.chat.realtime_chat_service import realtime_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["firebase_chat"])

@router.post("/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    message_data: ChatMessageCreate,
    current_user = Depends(get_current_user)
):
    """Send a chat message using Firebase"""
    try:
        # Send message via Firebase chat service
        message = await firebase_chat_service.send_message(current_user.user_id, message_data)
        
        return message
        
    except Exception as e:
        logger.error(f"Error sending chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )

@router.get("/conversations", response_model=List[ChatConversationResponse])
async def get_chat_conversations(
    current_user = Depends(get_current_user)
):
    """Get all conversations for the current user using Firebase"""
    try:
        conversations = await firebase_chat_service.get_user_conversations(current_user.user_id)
        return conversations
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversations"
        )

@router.get("/conversations/{other_user_id}/messages", response_model=List[ChatMessageResponse])
async def get_conversation_messages(
    other_user_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user)
):
    """Get messages in a conversation with another user using Firebase"""
    try:
        messages = await firebase_chat_service.get_conversation_messages(
            current_user.user_id, 
            other_user_id, 
            limit, 
            offset
        )
        
        # Mark messages as read
        await firebase_chat_service.mark_messages_as_read(current_user.user_id, other_user_id)
        
        return messages
        
    except Exception as e:
        logger.error(f"Error getting conversation messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )

@router.post("/messages/{message_id}/read", response_model=SuccessResponse)
async def mark_message_as_read(
    message_id: str,
    current_user = Depends(get_current_user)
):
    """Mark a message as read using Firebase"""
    try:
        # Get message details to find sender
        from app.core.database import get_supabase
        supabase = get_supabase()
        result = supabase.table("chat_messages").select("sender_id").eq("id", message_id).execute()
        
        if result.data:
            sender_id = result.data[0]["sender_id"]
            success = await firebase_chat_service.mark_messages_as_read(current_user.user_id, sender_id)
            
            if success:
                return {"success": True}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to mark message as read"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark message as read"
        )

@router.post("/messages/{message_id}/delivered", response_model=SuccessResponse)
async def mark_message_as_delivered(
    message_id: str,
    current_user = Depends(get_current_user)
):
    """Mark a message as delivered using Firebase"""
    try:
        success = await firebase_chat_service.mark_message_as_delivered(message_id)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to mark message as delivered"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking message as delivered: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark message as delivered"
        )

@router.delete("/messages/{message_id}", response_model=SuccessResponse)
async def delete_message(
    message_id: str,
    current_user = Depends(get_current_user)
):
    """Delete a message using Firebase"""
    try:
        success = await firebase_chat_service.delete_message(message_id, current_user.user_id)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own messages"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )

@router.get("/health", response_model=SuccessResponse)
async def chat_health_check():
    """Health check for chat service"""
    try:
        # Test chat service
        from app.services.chat.firebase_chat_service import firebase_chat_service
        
        # Check if Firebase is available
        if firebase_chat_service.db_ref:
            return {"success": True, "message": "Chat service is running with Firebase support"}
        else:
            return {"success": True, "message": "Chat service is running with Supabase only (Firebase not configured)"}
    except Exception as e:
        logger.error(f"Chat service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat service is not available"
        )


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time chat
    
    Connect to: ws://localhost:8000/chat/ws/{user_id}
    
    Message format:
    {
        "type": "message|typing|ping",
        "recipient_id": "uuid",
        "content": "message content",
        "message_type": "text",
        "metadata": {},
        "is_typing": true/false
    }
    """
    try:
        logger.info(f"WebSocket connection attempt for user: {user_id}")
        
        # Handle the WebSocket connection
        await realtime_chat_service.handle_websocket_connection(websocket, user_id)
        
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from WebSocket")
        realtime_chat_service.connection_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        realtime_chat_service.connection_manager.disconnect(user_id)


@router.get("/online-users", response_model=List[str])
async def get_online_users(current_user: TokenData = Depends(get_current_user)):
    """Get list of currently online users"""
    try:
        online_users = realtime_chat_service.get_connected_users()
        return online_users
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get online users"
        )


@router.get("/user-status/{user_id}")
async def check_user_status(user_id: str, current_user: TokenData = Depends(get_current_user)):
    """Check if a specific user is online"""
    try:
        is_online = realtime_chat_service.is_user_online(user_id)
        return {
            "user_id": user_id,
            "is_online": is_online,
            "status": "online" if is_online else "offline"
        }
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check user status"
        )


@router.get("/my-conversations", response_model=List[ChatConversationResponse])
async def get_my_conversations(
    current_user = Depends(get_current_user)
):
    """Get all conversations where the current user is either sender or receiver"""
    try:
        conversations = await firebase_chat_service.get_user_conversations_from_messages(current_user.user_id)
        return conversations
        
    except Exception as e:
        logger.error(f"Error getting user conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversations"
        )


@router.get("/conversation/{other_user_id}/history", response_model=List[ChatMessageResponse])
async def get_conversation_history(
    other_user_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user)
):
    """Get paginated chat history between current user and another user"""
    try:
        messages = await firebase_chat_service.get_conversation_history(
            current_user.user_id, 
            other_user_id, 
            limit, 
            offset
        )
        return messages
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation history"
        )
