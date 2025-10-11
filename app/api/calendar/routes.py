"""
Calendar API routes for Google Calendar integration
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

from app.core.config import settings
from app.core.security.auth_dependencies import get_current_user
from app.services.calendar.calendar_service import calendar_service
from app.services.calendar.calendar_credentials_service import calendar_credentials_service
from app.services.calendar.calendar_events_service import calendar_events_service
from app.services.calendar.batch_calendar_service import batch_calendar_service
from app.services.calendar.schedule_call_service import schedule_call_service
from app.services.calendar.payment_call_service import payment_call_service
from app.services.user.services import UserService
from app.utils.timezone_utils import timezone_utils
from app.models.models import (
    UserResponse, CalendarEventsResponse, CalendarSyncRequest,
    BatchFreeSlotsRequest, BatchFreeSlotsResponse,
    ScheduleCallRequest, ScheduledCall, PendingCallRequest, PaymentVerificationRequest
)

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = logging.getLogger(__name__)

# Initialize user service
user_service = UserService()

def _validate_calendar_oauth_config():
    """Validate Google Calendar OAuth configuration"""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured for calendar")
    
    # Check for calendar-specific redirect URI first, then fall back to general one
    calendar_redirect_uri = settings.google_calendar_redirect_uri or settings.google_redirect_uri
    if not calendar_redirect_uri:
        raise HTTPException(status_code=500, detail="Missing google_redirect_uri for calendar")

@router.get("/auth")
async def initiate_calendar_auth(current_user: UserResponse = Depends(get_current_user)):
    """Initiate Google Calendar OAuth flow to get calendar permissions"""
    try:
        _validate_calendar_oauth_config()
        
        user_id = str(current_user.user_id)
        
        # Check if user already has calendar credentials
        has_credentials = await calendar_credentials_service.has_calendar_credentials(user_id)
        
        if has_credentials:
            # User already has credentials, try to sync first
            try:
                credentials = await calendar_credentials_service.get_calendar_credentials(user_id)
                if credentials:
                    # Attempt to sync calendar events
                    sync_result = await calendar_service.sync_calendar_events(
                        user_id=user_id,
                        credentials_data=credentials
                    )
                    
                    # Update last sync time
                    await calendar_credentials_service.update_last_sync(user_id)
                    
                    return {
                        "already_connected": True,
                        "message": "Calendar already connected and synced successfully",
                        "sync_result": sync_result,
                        "user_id": user_id
                    }
            except Exception as sync_error:
                logger.warning(f"Failed to sync existing calendar for user {user_id}: {sync_error}")
                # If sync fails, we'll still redirect to re-authorize
                pass
        
        # Get authorization URL for calendar access
        auth_url = calendar_service.get_authorization_url(user_id)
        
        return {
            "authorization_url": auth_url,
            "already_connected": has_credentials,
            "message": "Redirect user to this URL to grant calendar permissions" if not has_credentials else "Re-authorizing calendar access",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Error initiating calendar auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate calendar authorization: {str(e)}"
        )

@router.get("/auth/force")
async def force_calendar_reauth(current_user: UserResponse = Depends(get_current_user)):
    """Force calendar re-authorization by clearing existing credentials first"""
    try:
        _validate_calendar_oauth_config()
        
        user_id = str(current_user.user_id)
        
        # Clear existing credentials first
        await calendar_credentials_service.revoke_calendar_credentials(user_id)
        
        # Get fresh authorization URL
        authorization_url = calendar_service.get_authorization_url(user_id)
        
        return {
            "authorization_url": authorization_url,
            "message": "Please complete calendar authorization with fresh permissions",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Error in force calendar re-authorization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to force calendar re-authorization: {str(e)}"
        )

@router.get("/auth-url")
async def get_calendar_auth_url(current_user: UserResponse = Depends(get_current_user)):
    """Get Google Calendar authorization URL as JSON response"""
    try:
        _validate_calendar_oauth_config()
        
        user_id = str(current_user.user_id)
        
        # Check if user already has calendar credentials
        has_credentials = await calendar_credentials_service.has_calendar_credentials(user_id)
        
        if has_credentials:
            # User already has credentials, try to sync first
            try:
                credentials = await calendar_credentials_service.get_calendar_credentials(user_id)
                if credentials:
                    # Attempt to sync calendar events
                    sync_result = await calendar_service.sync_calendar_events(
                        user_id=user_id,
                        credentials_data=credentials
                    )
                    
                    # Update last sync time
                    await calendar_credentials_service.update_last_sync(user_id)
                    
                    return {
                        "already_connected": True,
                        "message": "Calendar already connected and synced successfully",
                        "sync_result": sync_result,
                        "user_id": user_id,
                        "redirect_url": "/dashboard/mentor?tab=calls" if current_user.role == "mentor" else "/calls" if current_user.role == "mentee" else "/dashboard"
                    }
            except Exception as sync_error:
                logger.warning(f"Failed to sync existing calendar for user {user_id}: {sync_error}")
                # If sync fails, we'll still provide the auth URL for re-authorization
                pass
        
        # Get authorization URL for calendar access
        auth_url = calendar_service.get_authorization_url(user_id)
        
        # Return the OAuth URL as JSON instead of redirecting
        return {
            "authorization_url": auth_url,
            "already_connected": has_credentials,
            "message": "Use this URL to authorize calendar access" if not has_credentials else "Re-authorizing calendar access",
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Error getting calendar auth URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar authorization URL: {str(e)}"
        )

@router.get("/auth-redirect")
async def redirect_to_calendar_auth(current_user: UserResponse = Depends(get_current_user)):
    """Redirect directly to Google Calendar OAuth (for browser usage)"""
    try:
        _validate_calendar_oauth_config()
        
        user_id = str(current_user.user_id)
        
        # Check if user already has calendar credentials
        has_credentials = await calendar_credentials_service.has_calendar_credentials(user_id)
        
        if has_credentials:
            # User already has credentials, try to sync first
            try:
                credentials = await calendar_credentials_service.get_calendar_credentials(user_id)
                if credentials:
                    # Attempt to sync calendar events
                    sync_result = await calendar_service.sync_calendar_events(
                        user_id=user_id,
                        credentials_data=credentials
                    )
                    
                    # Update last sync time
                    await calendar_credentials_service.update_last_sync(user_id)
                    
                    # Redirect based on user role since already connected
                    if current_user.role == "mentor":
                        return RedirectResponse(url=f"{settings.frontend_url}/dashboard/mentor?tab=calls")
                    elif current_user.role == "mentee":
                        return RedirectResponse(url=f"{settings.frontend_url}/calls")
                    else:
                        return RedirectResponse(url=f"{settings.frontend_url}/dashboard")
            except Exception as sync_error:
                logger.warning(f"Failed to sync existing calendar for user {user_id}: {sync_error}")
                # If sync fails, we'll still redirect to re-authorize
                pass
        
        # Get authorization URL for calendar access
        auth_url = calendar_service.get_authorization_url(user_id)
        
        # Redirect directly to Google OAuth
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        logger.error(f"Error redirecting to calendar auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to redirect to calendar authorization: {str(e)}"
        )

@router.get("/callback")
async def calendar_callback(
    code: str, 
    state: Optional[str] = None, 
    error: Optional[str] = None
):
    """Handle Google Calendar OAuth callback"""
    try:
        _validate_calendar_oauth_config()
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google Calendar OAuth error: {error}"
            )
        
        if not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing state parameter"
            )
        
        # Extract user_id from state
        user_id = state
        
        # Exchange code for credentials
        credentials_data = calendar_service.exchange_code_for_credentials(code, user_id)
        
        # Store credentials in database
        credentials_stored = await calendar_credentials_service.store_calendar_credentials(user_id, credentials_data)
        
        if not credentials_stored:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store calendar credentials"
            )
        
        # Attempt to sync calendar events immediately after storing credentials
        sync_result = None
        try:
            sync_result = await calendar_service.sync_calendar_events(
                user_id=user_id,
                credentials_data=credentials_data
            )
            # Update last sync time
            await calendar_credentials_service.update_last_sync(user_id)
        except Exception as sync_error:
            logger.warning(f"Failed to sync calendar after authorization for user {user_id}: {sync_error}")
            # Don't fail the whole process if sync fails
        
        # Get user details to determine role-based redirect
        try:
            user = await user_service.get_user_by_id(user_id)
            if not user:
                logger.error(f"User not found for user_id: {user_id}")
                # Fallback to default redirect if user not found
                return RedirectResponse(url=f"{settings.frontend_url}/dashboard")
            
            # Redirect based on user role
            if user.role == "mentor":
                redirect_url = f"{settings.frontend_url}/dashboard/mentor?tab=calls"
            elif user.role == "mentee":
                redirect_url = f"{settings.frontend_url}/calls"
            else:
                # Default fallback for unknown roles
                redirect_url = f"{settings.frontend_url}/dashboard"
            
            logger.info(f"Redirecting user {user_id} (role: {user.role}) to {redirect_url}")
            return RedirectResponse(url=redirect_url)
            
        except Exception as user_error:
            logger.error(f"Error getting user details for redirect: {user_error}")
            # Fallback to default redirect if user lookup fails
            return RedirectResponse(url=f"{settings.frontend_url}/dashboard")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in calendar callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calendar authorization failed: {str(e)}"
        )

@router.get("/status")
async def get_calendar_status(current_user: UserResponse = Depends(get_current_user)):
    """Check if user has granted calendar permissions"""
    try:
        user_id = str(current_user.user_id)
        status_info = await calendar_credentials_service.get_calendar_status(user_id)
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error checking calendar status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check calendar status: {str(e)}"
        )

@router.post("/sync")
async def sync_calendar_events(current_user: UserResponse = Depends(get_current_user)):
    """Sync calendar events from Google Calendar"""
    try:
        user_id = str(current_user.user_id)
        
        # Get stored credentials for user
        credentials_data = await calendar_credentials_service.get_calendar_credentials(user_id)
        if not credentials_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Calendar not connected. Please authorize calendar access first."
            )
        
        # Sync calendar events
        sync_result = await calendar_service.sync_calendar_events(
            user_id=user_id,
            credentials_data=credentials_data
        )
        
        # Update last sync time
        await calendar_credentials_service.update_last_sync(user_id)
        
        return {
            "success": True,
            "message": "Calendar synced successfully",
            "user_id": user_id,
            "sync_result": sync_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync calendar: {str(e)}"
        )

@router.delete("/disconnect")
async def disconnect_calendar(current_user: UserResponse = Depends(get_current_user)):
    """Disconnect Google Calendar and remove stored credentials"""
    try:
        user_id = str(current_user.user_id)
        
        # Revoke stored credentials
        success = await calendar_credentials_service.revoke_calendar_credentials(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disconnect calendar"
            )
        
        return {
            "success": True,
            "message": "Calendar disconnected successfully",
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect calendar: {str(e)}"
        )

@router.post("/events", response_model=CalendarEventsResponse)
async def get_calendar_events(
    request: CalendarSyncRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get calendar events and analyze free/blocked slots for a user by email"""
    try:
        # Verify the requesting user has permission to access this email's calendar
        # For now, we'll allow users to access their own calendar
        if request.email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own calendar events"
            )
        
        # Get calendar events and slots
        result = await calendar_events_service.get_user_calendar_events(
            email=request.email,
            start_date=request.start_date,
            end_date=request.end_date,
            include_free_slots=request.include_free_slots,
            include_blocked_slots=request.include_blocked_slots
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calendar events for {request.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar events: {str(e)}"
        )

@router.get("/events/{email}", response_model=CalendarEventsResponse)
async def get_calendar_events_by_email(
    email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_free_slots: bool = True,
    include_blocked_slots: bool = True,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get calendar events and analyze free/blocked slots for a user by email (GET endpoint)"""
    try:
        # Verify the requesting user has permission to access this email's calendar
        if email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own calendar events"
            )
        
        # Get calendar events and slots
        result = await calendar_events_service.get_user_calendar_events(
            email=email,
            start_date=start_date,
            end_date=end_date,
            include_free_slots=include_free_slots,
            include_blocked_slots=include_blocked_slots
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calendar events for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar events: {str(e)}"
        )

@router.get("/test/database")
async def test_database_connection():
    """Test database connection for debugging"""
    try:
        connection_ok = await calendar_events_service.test_database_connection()
        if connection_ok:
            return {"status": "success", "message": "Database connection is working"}
        else:
            return {"status": "error", "message": "Database connection failed"}
    except Exception as e:
        logger.error(f"Database test error: {e}")
        return {"status": "error", "message": f"Database test failed: {str(e)}"}

@router.get("/test/credentials/{email}")
async def test_user_credentials(
    email: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Test if user has calendar credentials stored"""
    try:
        if email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own credentials"
            )

        # Test database connection first
        db_ok = await calendar_events_service.test_database_connection()
        if not db_ok:
            return {"status": "error", "message": "Database connection failed"}

        # Try to get credentials
        from app.core.database import get_supabase
        supabase = get_supabase()
        
        result = supabase.table("users").select(
            "user_id, email, google_calendar_credentials"
        ).eq("email", email).execute()

        if not result.data:
            return {"status": "error", "message": f"User not found: {email}"}

        user_data = result.data[0]
        credentials_data = user_data.get("google_calendar_credentials")

        if not credentials_data:
            return {"status": "error", "message": f"No calendar credentials found for: {email}"}

        return {
            "status": "success", 
            "message": "Credentials found",
            "user_id": user_data.get("user_id"),
            "email": user_data.get("email"),
            "has_credentials": bool(credentials_data),
            "credentials_type": type(credentials_data).__name__
        }

    except Exception as e:
        logger.error(f"Credentials test error: {e}")
        return {"status": "error", "message": f"Credentials test failed: {str(e)}"}

@router.get("/test/scheduled-calls-table")
async def test_scheduled_calls_table():
    """Test if scheduled_calls table exists"""
    try:
        from app.core.database import get_supabase
        supabase = get_supabase()
        
        # Try to query the scheduled_calls table
        result = supabase.table("scheduled_calls").select("id").limit(1).execute()
        
        return {
            "status": "success", 
            "message": "scheduled_calls table exists and is accessible",
            "table_exists": True
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"scheduled_calls table test failed: {str(e)}",
            "table_exists": False,
            "note": "Please run the database migration: database_migration_scheduled_calls.sql"
        }

@router.get("/test/mentor-lookup/{email}")
async def test_mentor_lookup(email: str):
    """Test mentor lookup functionality"""
    try:
        from app.core.database import get_supabase
        supabase = get_supabase()
        
        # Test the exact query used in schedule_call_service
        result = supabase.table("users").select(
            "user_id, email, name, role"
        ).eq("email", email).execute()
        
        if not result.data:
            return {
                "status": "error",
                "message": f"No user found for email: {email}",
                "query_result": result.data
            }
        
        user = result.data[0]
        return {
            "status": "success",
            "message": "User found",
            "user_data": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user.get("name", ""),
                "role": user["role"]
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Mentor lookup test failed: {str(e)}"
        }

@router.get("/test/calendar-data/{email}")
async def test_calendar_data_fetching(
    email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Comprehensive test for calendar data fetching functionality"""
    try:
        if email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only test your own calendar data"
            )

        test_results = {
            "email": email,
            "timestamp": datetime.utcnow().isoformat(),
            "tests": {}
        }

        # Test 1: Database Connection
        try:
            db_ok = await calendar_events_service.test_database_connection()
            test_results["tests"]["database_connection"] = {
                "status": "success" if db_ok else "failed",
                "message": "Database connection working" if db_ok else "Database connection failed"
            }
        except Exception as e:
            test_results["tests"]["database_connection"] = {
                "status": "failed",
                "message": f"Database test error: {str(e)}"
            }

        # Test 2: User Credentials Check
        try:
            from app.core.database import get_supabase
            supabase = get_supabase()
            
            result = supabase.table("users").select(
                "user_id, email, google_calendar_credentials"
            ).eq("email", email).execute()

            if not result.data:
                test_results["tests"]["user_credentials"] = {
                    "status": "failed",
                    "message": f"User not found: {email}"
                }
            else:
                user_data = result.data[0]
                credentials_data = user_data.get("google_calendar_credentials")
                
                test_results["tests"]["user_credentials"] = {
                    "status": "success" if credentials_data else "failed",
                    "message": "Credentials found" if credentials_data else "No calendar credentials found",
                    "user_id": user_data.get("user_id"),
                    "has_credentials": bool(credentials_data),
                    "credentials_type": type(credentials_data).__name__ if credentials_data else None
                }
        except Exception as e:
            test_results["tests"]["user_credentials"] = {
                "status": "failed",
                "message": f"Credentials check error: {str(e)}"
            }

        # Test 3: Calendar Events Fetching
        try:
            if test_results["tests"]["user_credentials"]["status"] == "success":
                # Set default date range
                if not start_date:
                    start_date = datetime.now().strftime("%Y-%m-%d")
                if not end_date:
                    end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

                # Attempt to fetch calendar events
                events_result = await calendar_events_service.get_user_calendar_events(
                    email=email,
                    start_date=start_date,
                    end_date=end_date,
                    include_free_slots=True,
                    include_blocked_slots=True
                )

                test_results["tests"]["calendar_events_fetch"] = {
                    "status": "success",
                    "message": "Calendar events fetched successfully",
                    "total_events": events_result.total_events,
                    "total_free_slots": events_result.total_free_slots,
                    "total_blocked_slots": events_result.total_blocked_slots,
                    "date_range": events_result.date_range,
                    "sample_events": [
                        {
                            "title": event.title,
                            "start_time": event.start_time.isoformat(),
                            "end_time": event.end_time.isoformat(),
                            "event_type": event.event_type.value
                        } for event in events_result.events[:3]  # First 3 events as sample
                    ]
                }
            else:
                test_results["tests"]["calendar_events_fetch"] = {
                    "status": "skipped",
                    "message": "Skipped due to missing credentials"
                }
        except Exception as e:
            test_results["tests"]["calendar_events_fetch"] = {
                "status": "failed",
                "message": f"Calendar events fetch error: {str(e)}"
            }

        # Test 4: Google Calendar API Connection
        try:
            if test_results["tests"]["user_credentials"]["status"] == "success":
                credentials = await calendar_events_service._get_user_calendar_credentials(email)
                if credentials:
                    # Test Google Calendar API connection
                    from googleapiclient.discovery import build
                    service = build('calendar', 'v3', credentials=credentials)
                    # Try to get calendar list to test API connection
                    calendar_list = service.calendarList().list().execute()
                    
                    test_results["tests"]["google_api_connection"] = {
                        "status": "success",
                        "message": "Google Calendar API connection successful",
                        "calendars_count": len(calendar_list.get('items', [])),
                        "primary_calendar": next(
                            (cal for cal in calendar_list.get('items', []) if cal.get('primary')), 
                            {}
                        ).get('id', 'Not found')
                    }
                else:
                    test_results["tests"]["google_api_connection"] = {
                        "status": "failed",
                        "message": "Could not create credentials object"
                    }
            else:
                test_results["tests"]["google_api_connection"] = {
                    "status": "skipped",
                    "message": "Skipped due to missing credentials"
                }
        except Exception as e:
            test_results["tests"]["google_api_connection"] = {
                "status": "failed",
                "message": f"Google API connection error: {str(e)}"
            }

        # Overall status
        failed_tests = [test for test, result in test_results["tests"].items() 
                       if result["status"] == "failed"]
        test_results["overall_status"] = "success" if not failed_tests else "failed"
        test_results["failed_tests"] = failed_tests

        return test_results

    except Exception as e:
        logger.error(f"Calendar data test error: {e}")
        return {
            "status": "error",
            "message": f"Calendar data test failed: {str(e)}"
        }

@router.get("/test/calendar-health")
async def test_calendar_health_check(current_user: UserResponse = Depends(get_current_user)):
    """Comprehensive health check for calendar functionality"""
    try:
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(current_user.user_id),
            "email": current_user.email,
            "checks": {}
        }

        # Check 1: Calendar Connection Status
        try:
            status_info = await calendar_credentials_service.get_calendar_status(str(current_user.user_id))
            health_status["checks"]["calendar_connection"] = status_info
        except Exception as e:
            health_status["checks"]["calendar_connection"] = {
                "status": "error",
                "message": f"Connection check failed: {str(e)}"
            }

        # Check 2: Recent Sync Status
        try:
            credentials = await calendar_credentials_service.get_calendar_credentials(str(current_user.user_id))
            if credentials:
                last_sync = credentials.get("last_sync")
                stored_at = credentials.get("stored_at")
                
                health_status["checks"]["sync_status"] = {
                    "has_credentials": True,
                    "last_sync": last_sync,
                    "credentials_stored_at": stored_at,
                    "sync_age_hours": None
                }
                
                if last_sync:
                    try:
                        last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                        sync_age = datetime.utcnow() - last_sync_dt
                        health_status["checks"]["sync_status"]["sync_age_hours"] = sync_age.total_seconds() / 3600
                    except:
                        pass
            else:
                health_status["checks"]["sync_status"] = {
                    "has_credentials": False,
                    "message": "No calendar credentials found"
                }
        except Exception as e:
            health_status["checks"]["sync_status"] = {
                "status": "error",
                "message": f"Sync status check failed: {str(e)}"
            }

        # Check 3: Database Health
        try:
            db_ok = await calendar_events_service.test_database_connection()
            health_status["checks"]["database_health"] = {
                "status": "healthy" if db_ok else "unhealthy",
                "message": "Database connection working" if db_ok else "Database connection failed"
            }
        except Exception as e:
            health_status["checks"]["database_health"] = {
                "status": "error",
                "message": f"Database health check failed: {str(e)}"
            }

        return health_status

    except Exception as e:
        logger.error(f"Calendar health check error: {e}")
        return {
            "status": "error",
            "message": f"Calendar health check failed: {str(e)}"
        }

@router.get("/test/validate-data/{email}")
async def validate_calendar_data_integrity(
    email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Validate calendar data integrity and provide detailed analysis"""
    try:
        if email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only validate your own calendar data"
            )

        # Set default date range
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Run validation
        validation_results = await calendar_events_service.validate_calendar_data_integrity(
            email=email,
            start_date=start_date,
            end_date=end_date
        )

        return validation_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calendar data validation error: {e}")
        return {
            "status": "error",
            "message": f"Calendar data validation failed: {str(e)}"
        }

@router.get("/test/data-summary/{email}")
async def get_calendar_data_summary(
    email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get comprehensive calendar data summary and analytics"""
    try:
        if email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own calendar data summary"
            )

        # Set default date range
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        # Get data summary
        summary = await calendar_events_service.get_calendar_data_summary(
            email=email,
            start_date=start_date,
            end_date=end_date
        )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calendar data summary error: {e}")
        return {
            "status": "error",
            "message": f"Calendar data summary failed: {str(e)}"
        }

@router.get("/test/sync-monitoring")
async def get_calendar_sync_monitoring(current_user: UserResponse = Depends(get_current_user)):
    """Monitor calendar sync status and provide detailed sync information"""
    try:
        user_id = str(current_user.user_id)
        email = current_user.email
        
        monitoring_data = {
            "user_id": user_id,
            "email": email,
            "monitoring_timestamp": datetime.utcnow().isoformat(),
            "sync_status": {}
        }
        
        # Check credentials status
        try:
            credentials = await calendar_credentials_service.get_calendar_credentials(user_id)
            if credentials:
                last_sync = credentials.get("last_sync")
                stored_at = credentials.get("stored_at")
                
                # Calculate sync age
                sync_age_hours = None
                if last_sync:
                    try:
                        last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                        sync_age = datetime.utcnow() - last_sync_dt
                        sync_age_hours = sync_age.total_seconds() / 3600
                    except:
                        pass
                
                monitoring_data["sync_status"]["credentials"] = {
                    "status": "connected",
                    "last_sync": last_sync,
                    "sync_age_hours": sync_age_hours,
                    "credentials_stored_at": stored_at,
                    "sync_freshness": "fresh" if sync_age_hours and sync_age_hours < 24 else "stale" if sync_age_hours else "unknown"
                }
            else:
                monitoring_data["sync_status"]["credentials"] = {
                    "status": "not_connected",
                    "message": "No calendar credentials found"
                }
        except Exception as e:
            monitoring_data["sync_status"]["credentials"] = {
                "status": "error",
                "message": f"Error checking credentials: {str(e)}"
            }
        
        # Test current sync capability
        try:
            if monitoring_data["sync_status"]["credentials"]["status"] == "connected":
                # Test a small data fetch to verify sync is working
                test_start = datetime.now().strftime("%Y-%m-%d")
                test_end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                
                try:
                    test_result = await calendar_events_service.get_user_calendar_events(
                        email=email,
                        start_date=test_start,
                        end_date=test_end,
                        include_free_slots=False,
                        include_blocked_slots=False
                    )
                    
                    monitoring_data["sync_status"]["current_sync_test"] = {
                        "status": "success",
                        "message": "Calendar sync is working",
                        "test_events_count": test_result.total_events,
                        "test_date_range": {"start": test_start, "end": test_end}
                    }
                except Exception as sync_error:
                    monitoring_data["sync_status"]["current_sync_test"] = {
                        "status": "failed",
                        "message": f"Sync test failed: {str(sync_error)}",
                        "error_type": type(sync_error).__name__
                    }
            else:
                monitoring_data["sync_status"]["current_sync_test"] = {
                    "status": "skipped",
                    "message": "Skipped due to missing credentials"
                }
        except Exception as e:
            monitoring_data["sync_status"]["current_sync_test"] = {
                "status": "error",
                "message": f"Sync test error: {str(e)}"
            }
        
        # Overall sync health assessment
        credentials_ok = monitoring_data["sync_status"]["credentials"]["status"] == "connected"
        sync_test_ok = monitoring_data["sync_status"]["current_sync_test"]["status"] == "success"
        
        if credentials_ok and sync_test_ok:
            monitoring_data["overall_sync_health"] = "healthy"
        elif credentials_ok and not sync_test_ok:
            monitoring_data["overall_sync_health"] = "credentials_ok_sync_failing"
        elif not credentials_ok:
            monitoring_data["overall_sync_health"] = "not_connected"
        else:
            monitoring_data["overall_sync_health"] = "unknown"
        
        return monitoring_data
        
    except Exception as e:
        logger.error(f"Calendar sync monitoring error: {e}")
        return {
            "status": "error",
            "message": f"Calendar sync monitoring failed: {str(e)}"
        }

@router.get("/profile/{mentor_email}/available-slots")
async def get_mentor_available_slots(
    mentor_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    duration_minutes: int = 30,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available time slots for a mentor's profile (for mentees to view)"""
    try:
        logger.info(f"Getting available slots for mentor {mentor_email} requested by {current_user.email}")
        
        # Set default date range (next 7 days)
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Validate duration
        if duration_minutes not in [15, 30, 45, 60, 90, 120]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be one of: 15, 30, 45, 60, 90, 120 minutes"
            )
        
        # Get mentor's available slots
        result = await calendar_events_service.get_user_calendar_events(
            email=mentor_email,
            start_date=start_date,
            end_date=end_date,
            include_free_slots=True,
            include_blocked_slots=False  # Don't include blocked slots for profile viewing
        )
        
        # Filter and format free slots for the requested duration
        available_slots = []
        for slot in result.free_slots:
            slot_duration = (slot.end_time - slot.start_time).total_seconds() / 60
            
            # Only include slots that are long enough for the requested duration
            if slot_duration >= duration_minutes:
                available_slots.append({
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "duration_minutes": int(slot_duration),
                    "is_available": slot.is_available,
                    "slot_id": f"{mentor_email}_{slot.start_time.strftime('%Y%m%d_%H%M')}"
                })
        
        return {
            "mentor_email": mentor_email,
            "requested_by": current_user.email,
            "date_range": {"start": start_date, "end": end_date},
            "duration_minutes": duration_minutes,
            "total_available_slots": len(available_slots),
            "available_slots": available_slots,
            "fetched_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mentor available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mentor available slots: {str(e)}"
        )

@router.post("/profile/schedule-call")
async def schedule_call_after_payment(
    request: dict,
    current_user: UserResponse = Depends(get_current_user)
):
    """Schedule a call after payment completion"""
    try:
        # Extract required fields from request
        mentor_email = request.get("mentor_email")
        mentee_email = current_user.email
        mentee_id = str(current_user.user_id)
        selected_slot = request.get("selected_slot")
        payment_id = request.get("payment_id")
        payment_status = request.get("payment_status")
        
        # Validate required fields
        if not mentor_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mentor_email is required"
            )
        
        if not selected_slot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_slot is required"
            )
        
        if not payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payment_id is required"
            )
        
        if payment_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment must be completed before scheduling call"
            )
        
        # Parse selected slot
        try:
            start_time = datetime.fromisoformat(selected_slot["start_time"])
            end_time = datetime.fromisoformat(selected_slot["end_time"])
        except (ValueError, KeyError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid selected_slot format: {str(e)}"
            )
        
        # Validate slot is in the future
        if start_time <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected slot must be in the future"
            )
        
        logger.info(f"Scheduling call between {mentee_email} and {mentor_email} for {start_time}")
        
        # Create schedule call request
        schedule_request = ScheduleCallRequest(
            mentor_email=mentor_email,
            start_time=start_time,
            end_time=end_time,
            title=f"Call between {mentee_email} and {mentor_email}",
            description=f"Scheduled call via Mentto platform"
        )
        
        # Schedule the call
        scheduled_call = await schedule_call_service.schedule_call(
            mentee_id=mentee_id,
            mentee_email=mentee_email,
            request=schedule_request
        )
        
        return {
            "success": True,
            "message": "Call scheduled successfully",
            "call_id": scheduled_call.call_id,
            "mentor_email": mentor_email,
            "mentee_email": mentee_email,
            "start_time": scheduled_call.start_time.isoformat(),
            "end_time": scheduled_call.end_time.isoformat(),
            "status": scheduled_call.status,
            "meeting_link": scheduled_call.meeting_link,
            "scheduled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling call after payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule call: {str(e)}"
        )

@router.get("/profile/{mentor_email}/available-slots-multi-duration")
async def get_mentor_available_slots_multi_duration(
    mentor_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available time slots for multiple durations (15, 30, 45, 60, 90, 120 minutes)"""
    try:
        logger.info(f"Getting multi-duration available slots for mentor {mentor_email} requested by {current_user.email}")
        
        # Set default date range (next 7 days)
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Get mentor's calendar data once
        result = await calendar_events_service.get_user_calendar_events(
            email=mentor_email,
            start_date=start_date,
            end_date=end_date,
            include_free_slots=True,
            include_blocked_slots=False
        )
        
        # Available durations to check
        durations = [15, 30, 45, 60, 90, 120]
        multi_duration_slots = {}
        
        for duration in durations:
            available_slots = []
            for slot in result.free_slots:
                slot_duration = (slot.end_time - slot.start_time).total_seconds() / 60
                
                # Only include slots that are long enough for this duration
                if slot_duration >= duration:
                    available_slots.append({
                        "start_time": slot.start_time.isoformat(),
                        "end_time": slot.end_time.isoformat(),
                        "duration_minutes": int(slot_duration),
                        "is_available": slot.is_available,
                        "slot_id": f"{mentor_email}_{slot.start_time.strftime('%Y%m%d_%H%M')}_{duration}min"
                    })
            
            multi_duration_slots[f"{duration}_minutes"] = {
                "duration_minutes": duration,
                "total_available_slots": len(available_slots),
                "available_slots": available_slots
            }
        
        return {
            "mentor_email": mentor_email,
            "requested_by": current_user.email,
            "date_range": {"start": start_date, "end": end_date},
            "duration_options": multi_duration_slots,
            "fetched_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting multi-duration mentor available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get multi-duration mentor available slots: {str(e)}"
        )

@router.get("/profile/{mentor_email}/available-slots-timezone")
async def get_mentor_available_slots_timezone_aware(
    mentor_email: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    duration_minutes: int = 30,
    user_timezone: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get available time slots with timezone conversion for global users"""
    try:
        logger.info(f"Getting timezone-aware available slots for mentor {mentor_email} requested by {current_user.email}")
        
        # Get user's timezone (from profile or request)
        user_tz = user_timezone or getattr(current_user, 'timezone', 'UTC')
        user_tz = timezone_utils.get_user_timezone(user_tz)
        
        # Set default date range (next 7 days)
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # If same day is requested, extend end_date to next day to include full day
        if start_date == end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = start_dt + timedelta(days=1)
            end_date = end_dt.strftime("%Y-%m-%d")
        
        # Validate duration
        if duration_minutes not in [15, 30, 45, 60, 90, 120]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be one of: 15, 30, 45, 60, 90, 120 minutes"
            )
        
        # Get mentor's available slots (in UTC)
        result = await calendar_events_service.get_user_calendar_events(
            email=mentor_email,
            start_date=start_date,
            end_date=end_date,
            include_free_slots=True,
            include_blocked_slots=False
        )
        
        # Convert slots to user's timezone and break down large slots
        available_slots = []
        for slot in result.free_slots:
            slot_duration = (slot.end_time - slot.start_time).total_seconds() / 60
            
            # Only include slots that are long enough for the requested duration
            if slot_duration >= duration_minutes:
                # Convert UTC times to user's timezone
                start_time_user_tz = timezone_utils.convert_from_utc(slot.start_time, user_tz)
                end_time_user_tz = timezone_utils.convert_from_utc(slot.end_time, user_tz)
                
                # If slot is much longer than requested duration, break it down
                if slot_duration > duration_minutes * 2:  # If more than 2x requested duration
                    # Create multiple bookable slots within this large free period
                    current_start = slot.start_time
                    slot_count = 0
                    max_slots = 10  # Limit to prevent too many slots
                    
                    while current_start < slot.end_time and slot_count < max_slots:
                        # Calculate end time for this sub-slot
                        current_end = current_start + timedelta(minutes=duration_minutes)
                        
                        # Don't exceed the original slot end time
                        if current_end > slot.end_time:
                            break
                        
                        # Convert to user timezone
                        current_start_user = timezone_utils.convert_from_utc(current_start, user_tz)
                        current_end_user = timezone_utils.convert_from_utc(current_end, user_tz)
                        
                        available_slots.append({
                            "start_time": current_start_user.isoformat(),
                            "end_time": current_end_user.isoformat(),
                            "start_time_utc": current_start.isoformat(),
                            "end_time_utc": current_end.isoformat(),
                            "duration_minutes": duration_minutes,
                            "is_available": True,
                            "slot_id": f"{mentor_email}_{current_start.strftime('%Y%m%d_%H%M')}_{duration_minutes}min",
                            "timezone_info": {
                                "user_timezone": user_tz,
                                "utc_offset": timezone_utils.get_timezone_info(user_tz)['utc_offset'],
                                "display_time": timezone_utils.format_datetime_for_timezone(
                                    current_start, user_tz, "%Y-%m-%d %H:%M %Z"
                                )
                            }
                        })
                        
                        # Move to next slot (with 15-minute buffer to avoid back-to-back bookings)
                        current_start = current_end + timedelta(minutes=15)
                        slot_count += 1
                else:
                    # Use the original slot as-is
                    available_slots.append({
                        "start_time": start_time_user_tz.isoformat(),
                        "end_time": end_time_user_tz.isoformat(),
                        "start_time_utc": slot.start_time.isoformat(),
                        "end_time_utc": slot.end_time.isoformat(),
                        "duration_minutes": int(slot_duration),
                        "is_available": slot.is_available,
                        "slot_id": f"{mentor_email}_{slot.start_time.strftime('%Y%m%d_%H%M')}",
                        "timezone_info": {
                            "user_timezone": user_tz,
                            "utc_offset": timezone_utils.get_timezone_info(user_tz)['utc_offset'],
                            "display_time": timezone_utils.format_datetime_for_timezone(
                                slot.start_time, user_tz, "%Y-%m-%d %H:%M %Z"
                            )
                        }
                    })
        
        return {
            "mentor_email": mentor_email,
            "requested_by": current_user.email,
            "user_timezone": user_tz,
            "date_range": {"start": start_date, "end": end_date},
            "duration_minutes": duration_minutes,
            "total_available_slots": len(available_slots),
            "available_slots": available_slots,
            "timezone_info": timezone_utils.get_timezone_info(user_tz),
            "fetched_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting timezone-aware mentor available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timezone-aware mentor available slots: {str(e)}"
        )

@router.post("/profile/schedule-call-timezone")
async def schedule_call_after_payment_timezone_aware(
    request: dict,
    current_user: UserResponse = Depends(get_current_user)
):
    """Schedule a call with timezone awareness after payment completion"""
    try:
        # Extract required fields from request
        mentor_email = request.get("mentor_email")
        mentee_email = current_user.email
        mentee_id = str(current_user.user_id)
        selected_slot = request.get("selected_slot")
        payment_id = request.get("payment_id")
        payment_status = request.get("payment_status")
        user_timezone = request.get("user_timezone", getattr(current_user, 'timezone', 'UTC'))
        
        # Validate required fields
        if not mentor_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mentor_email is required"
            )
        
        if not selected_slot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_slot is required"
            )
        
        if not payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="payment_id is required"
            )
        
        if payment_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment must be completed before scheduling call"
            )
        
        # Parse selected slot with timezone handling
        try:
            # Check if slot is already in UTC or user timezone
            if "start_time_utc" in selected_slot and "end_time_utc" in selected_slot:
                # Use UTC times directly
                start_time = datetime.fromisoformat(selected_slot["start_time_utc"].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(selected_slot["end_time_utc"].replace('Z', '+00:00'))
            else:
                # Convert from user timezone to UTC
                start_time = datetime.fromisoformat(selected_slot["start_time"])
                end_time = datetime.fromisoformat(selected_slot["end_time"])
                
                # Convert to UTC if times are in user timezone
                start_time = timezone_utils.convert_to_utc(start_time, user_timezone)
                end_time = timezone_utils.convert_to_utc(end_time, user_timezone)
            
            # Ensure both times are timezone-aware
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=None)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=None)
                
        except (ValueError, KeyError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid selected_slot format: {str(e)}"
            )
        
        # Validate slot is in the future
        now_utc = datetime.utcnow().replace(tzinfo=None)
        if start_time.replace(tzinfo=None) <= now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected slot must be in the future"
            )
        
        logger.info(f"Scheduling timezone-aware call between {mentee_email} and {mentor_email} for {start_time}")
        
        # Create schedule call request
        schedule_request = ScheduleCallRequest(
            mentor_email=mentor_email,
            start_time=start_time,
            end_time=end_time,
            title=f"Call between {mentee_email} and {mentor_email}",
            description=f"Scheduled call via Mentto platform (User timezone: {user_timezone})"
        )
        
        # Schedule the call
        scheduled_call = await schedule_call_service.schedule_call(
            mentee_id=mentee_id,
            mentee_email=mentee_email,
            request=schedule_request
        )
        
        # Convert times back to user timezone for response
        start_time_user = timezone_utils.convert_from_utc(scheduled_call.start_time, user_timezone)
        end_time_user = timezone_utils.convert_from_utc(scheduled_call.end_time, user_timezone)
        
        return {
            "success": True,
            "message": "Call scheduled successfully with timezone awareness",
            "call_id": scheduled_call.id,
            "mentor_email": mentor_email,
            "mentee_email": mentee_email,
            "start_time_utc": scheduled_call.start_time.isoformat(),
            "end_time_utc": scheduled_call.end_time.isoformat(),
            "start_time_user_tz": start_time_user.isoformat(),
            "end_time_user_tz": end_time_user.isoformat(),
            "user_timezone": user_timezone,
            "status": scheduled_call.status,
            "meeting_link": scheduled_call.meeting_link,
            "timezone_info": {
                "user_timezone": user_timezone,
                "utc_offset": timezone_utils.get_timezone_info(user_timezone)['utc_offset'],
                "display_time": timezone_utils.format_datetime_for_timezone(
                    scheduled_call.start_time, user_timezone, "%Y-%m-%d %H:%M %Z"
                )
            },
            "scheduled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling timezone-aware call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule timezone-aware call: {str(e)}"
        )

@router.get("/timezones")
async def get_available_timezones():
    """Get list of available timezones"""
    try:
        return {
            "timezones": timezone_utils.get_available_timezones(),
            "default_timezone": "UTC"
        }
    except Exception as e:
        logger.error(f"Error getting timezones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timezones: {str(e)}"
        )

@router.get("/timezone-info/{timezone_name}")
async def get_timezone_info(timezone_name: str):
    """Get information about a specific timezone"""
    try:
        timezone_info = timezone_utils.get_timezone_info(timezone_name)
        return timezone_info
    except Exception as e:
        logger.error(f"Error getting timezone info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timezone info: {str(e)}"
        )

@router.post("/events/batch-free-slots", response_model=BatchFreeSlotsResponse)
async def get_batch_free_slots(
    request: BatchFreeSlotsRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get free slots for multiple mentors"""
    try:
        logger.info(f"Getting batch free slots for {len(request.mentor_emails)} mentors")
        
        # Validate that we have mentor emails
        if not request.mentor_emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one mentor email is required"
            )
        
        # Limit the number of mentors to prevent performance issues
        if len(request.mentor_emails) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 mentors can be queried at once"
            )
        
        # Get batch free slots
        result = await batch_calendar_service.get_batch_free_slots(
            mentor_emails=request.mentor_emails,
            start_date=request.start_date,
            end_date=request.end_date,
            duration_minutes=request.duration_minutes
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch free slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get batch free slots: {str(e)}"
        )

@router.post("/schedule/call", response_model=ScheduledCall)
async def schedule_call(
    request: ScheduleCallRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Schedule a call between mentee and mentor"""
    try:
        logger.info(f"Scheduling call between {current_user.email} and {request.mentor_email}")
        
        # Validate request
        if request.start_time >= request.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time"
            )
        
        # Make start_time timezone-aware for comparison
        if request.start_time.tzinfo is None:
            start_time_aware = request.start_time.replace(tzinfo=None)
        else:
            start_time_aware = request.start_time.replace(tzinfo=None)
        
        if start_time_aware <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be in the future"
            )
        
        # Schedule the call
        result = await schedule_call_service.schedule_call(
            mentee_id=str(current_user.user_id),
            mentee_email=current_user.email,
            request=request
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule call: {str(e)}"
        )

@router.get("/schedule/calls", response_model=List[ScheduledCall])
async def get_scheduled_calls(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get scheduled calls for the current user"""
    try:
        calls = await schedule_call_service.get_user_scheduled_calls(
            user_id=str(current_user.user_id),
            status=status,
            limit=limit,
            offset=offset
        )
        
        return calls
        
    except Exception as e:
        logger.error(f"Error getting scheduled calls: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scheduled calls: {str(e)}"
        )

@router.delete("/schedule/call/{call_id}")
async def cancel_call(
    call_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Cancel a scheduled call"""
    try:
        success = await schedule_call_service.cancel_call(
            call_id=call_id,
            user_id=str(current_user.user_id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to cancel call"
            )
        
        return {"success": True, "message": "Call cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel call: {str(e)}"
        )

@router.post("/schedule/call/pending")
async def create_pending_call(
    request: PendingCallRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a call with pending payment status"""
    try:
        logger.info(f"Creating pending call between {current_user.email} and {request.mentor_email}")
        
        # Validate request
        if request.start_time >= request.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time"
            )
        
        # Make start_time timezone-aware for comparison
        if request.start_time.tzinfo is None:
            start_time_aware = request.start_time.replace(tzinfo=None)
        else:
            start_time_aware = request.start_time.replace(tzinfo=None)
        
        if start_time_aware <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be in the future"
            )
        
        # Create pending call
        result = await payment_call_service.create_pending_call(
            mentee_id=str(current_user.user_id),
            mentee_email=current_user.email,
            request=request
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating pending call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create pending call: {str(e)}"
        )

@router.post("/schedule/call/verify-payment", response_model=ScheduledCall)
async def verify_payment_and_confirm_call(
    request: PaymentVerificationRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Verify payment and confirm the call"""
    try:
        logger.info(f"Verifying payment for call {request.call_id}")
        
        # Verify payment and confirm call
        result = await payment_call_service.verify_payment_and_confirm_call(request)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify payment: {str(e)}"
        )

@router.get("/schedule/call/{call_id}/status", response_model=ScheduledCall)
async def get_call_status(
    call_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get the status of a scheduled call"""
    try:
        # Get call details
        result = await payment_call_service._get_scheduled_call(call_id)
        
        # Check if user has access to this call
        if (result.mentee_id != str(current_user.user_id) and 
            result.mentor_id != str(current_user.user_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own calls"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call status: {str(e)}"
        )
