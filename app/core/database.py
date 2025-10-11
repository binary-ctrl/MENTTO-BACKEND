from supabase import create_client, Client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_supabase() -> Client:
    """Create and return a Supabase client for regular operations on demand."""
    try:
        from supabase.lib.client_options import ClientOptions
        options = ClientOptions()
        return create_client(settings.supabase_url, settings.supabase_key, options)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        raise

def get_supabase_admin() -> Client:
    """Create and return a Supabase client with service role on demand."""
    try:
        from supabase.lib.client_options import ClientOptions
        options = ClientOptions()
        return create_client(settings.supabase_url, settings.supabase_service_role_key, options)
    except Exception as e:
        logger.error(f"Failed to create Supabase admin client: {e}")
        raise
