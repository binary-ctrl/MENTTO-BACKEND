"""
URL utility functions for consistent URL formatting across the application.
"""

from app.core.config import settings


def format_frontend_url(path: str = "") -> str:
    """
    Format a frontend URL with proper protocol and path.
    
    Args:
        path: The path to append to the frontend URL (e.g., "/auth", "/dashboard")
        
    Returns:
        A properly formatted URL with protocol
        
    Examples:
        format_frontend_url("/auth") -> "https://staging.mentto.in/auth"
        format_frontend_url("dashboard") -> "https://staging.mentto.in/dashboard"
        format_frontend_url() -> "https://staging.mentto.in"
    """
    base_url = settings.frontend_url.rstrip('/')
    
    # Ensure protocol is present
    if not base_url.startswith(('http://', 'https://')):
        base_url = f"https://{base_url}"
    
    # Add path if provided
    if path:
        path = path.lstrip('/')
        return f"{base_url}/{path}"
    
    return base_url


def format_auth_url() -> str:
    """
    Format the authentication URL for the frontend.
    
    Returns:
        A properly formatted authentication URL
    """
    return format_frontend_url("/auth")


def format_dashboard_url(role: str = None, tab: str = None) -> str:
    """
    Format a dashboard URL based on user role and optional tab.
    
    Args:
        role: User role ("mentor" or "mentee")
        tab: Optional tab parameter
        
    Returns:
        A properly formatted dashboard URL
    """
    if role == "mentor":
        path = "/dashboard/mentor"
        if tab:
            path += f"?tab={tab}"
        return format_frontend_url(path)
    elif role == "mentee":
        return format_frontend_url("/calls")
    else:
        return format_frontend_url("/dashboard")
