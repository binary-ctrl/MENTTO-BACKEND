import uuid
import os
import logging
from typing import Optional
from fastapi import HTTPException, status, UploadFile
from app.core.config import settings
from app.core.database import get_supabase_admin

logger = logging.getLogger(__name__)


class FileUploadService:
    def __init__(self):
        self.supabase = get_supabase_admin()

    async def upload_profile_picture(
        self, 
        file: UploadFile, 
        user_id: str
    ) -> str:
        """Upload profile picture to storage bucket and return public URL"""
        try:
            # Validate file
            await self._validate_file(file)
            
            # Generate unique filename
            file_extension = self._get_file_extension(file.filename)
            unique_filename = f"{user_id}_{uuid.uuid4()}{file_extension}"
            
            # Read file content
            file_content = await file.read()
            
            # Upload to Supabase Storage
            upload_path = f"profile_pictures/{unique_filename}"
            
            logger.info(f"Uploading file to bucket '{settings.storage_bucket_name}' at path '{upload_path}'")
            logger.info(f"File size: {len(file_content)} bytes, Content type: {file.content_type}")
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(settings.storage_bucket_name).upload(
                path=upload_path,
                file=file_content,
                file_options={
                    "content-type": file.content_type,
                    "cache-control": "3600",
                    "upsert": "true"  # Replace if exists
                }
            )
            
            logger.info(f"Upload result type: {type(result)}, result: {result}")

            # Handle response for supabase-py which may return httpx.Response or dict
            upload_success = False
            if hasattr(result, "status_code"):
                # Likely an httpx.Response
                status_code = int(getattr(result, "status_code", 500))
                if status_code >= 400:
                    try:
                        error_payload = result.json()
                    except Exception:
                        error_payload = getattr(result, "text", "Unknown error")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to upload file: {error_payload}"
                    )
                elif status_code in [200, 201]:
                    upload_success = True
            elif isinstance(result, dict):
                error_value = result.get("error") or result.get("Error")
                if error_value:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to upload file: {error_value}"
                    )
                else:
                    upload_success = True
            else:
                # Unknown response type, assume success if no exception
                upload_success = True
            
            if not upload_success:
                logger.error(f"File upload failed. Result: {result}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="File upload did not succeed. Please check storage configuration and bucket permissions."
                )
            
            logger.info(f"File upload successful. Path: {upload_path}")
            
            # Get public URL
            try:
                public_url_result = self.supabase.storage.from_(settings.storage_bucket_name).get_public_url(upload_path)
                logger.info(f"Public URL result type: {type(public_url_result)}, result: {public_url_result}")
            except Exception as url_error:
                logger.error(f"Error getting public URL: {url_error}")
                # Fallback to manual construction
                public_url_result = None

            # Support both string and dict shapes
            public_url = None
            if isinstance(public_url_result, str):
                public_url = public_url_result
            elif isinstance(public_url_result, dict):
                data_section = public_url_result.get("data") or public_url_result
                public_url = (
                    (data_section.get("publicUrl") if isinstance(data_section, dict) else None)
                    or data_section.get("public_url") if isinstance(data_section, dict) else None
                )
            
            # Fallback: construct manually if API didn't return URL
            if not public_url:
                public_url = f"{settings.supabase_url}/storage/v1/object/public/{settings.storage_bucket_name}/{upload_path}"
            
            logger.info(f"Final public URL: {public_url}")
            
            return public_url
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File upload failed: {str(e)}"
            )

    async def delete_profile_picture(self, profile_pic_url: str) -> bool:
        """Delete profile picture from storage"""
        try:
            if not profile_pic_url:
                return True
            
            # Extract file path from URL
            file_path = self._extract_file_path_from_url(profile_pic_url)
            
            if not file_path:
                return True
            
            # Delete from storage
            result = self.supabase.storage.from_(settings.storage_bucket_name).remove([file_path])

            if hasattr(result, "status_code"):
                if int(getattr(result, "status_code", 500)) >= 400:
                    try:
                        error_payload = result.json()
                    except Exception:
                        error_payload = getattr(result, "text", "Unknown error")
                    print(f"Failed to delete file: {error_payload}")
                    return False
            elif isinstance(result, dict):
                error_value = result.get("error") or result.get("Error")
                if error_value:
                    print(f"Failed to delete file: {error_value}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error deleting file: {str(e)}")
            return False

    async def _validate_file(self, file: UploadFile):
        """Validate uploaded file"""
        # Check file size
        if file.size and file.size > settings.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {settings.max_file_size / (1024*1024):.1f}MB"
            )
        
        # Check file type
        if file.content_type not in settings.allowed_file_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.allowed_file_types)}"
            )
        
        # Check file extension
        if not file.filename or not self._is_valid_extension(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file extension. Allowed: .jpg, .jpeg, .png, .webp"
            )

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        if not filename:
            return ".jpg"
        
        _, ext = os.path.splitext(filename.lower())
        return ext if ext else ".jpg"

    def _is_valid_extension(self, filename: str) -> bool:
        """Check if file extension is valid"""
        valid_extensions = [".jpg", ".jpeg", ".png", ".webp"]
        _, ext = os.path.splitext(filename.lower())
        return ext in valid_extensions

    def _extract_file_path_from_url(self, url: str) -> Optional[str]:
        """Extract file path from Supabase storage URL"""
        try:
            # Supabase storage URL format: https://[project].supabase.co/storage/v1/object/public/[bucket]/[path]
            if "/storage/v1/object/public/" in url:
                parts = url.split("/storage/v1/object/public/")
                if len(parts) > 1:
                    path_part = parts[1]
                    # Remove bucket name from path
                    if path_part.startswith(f"{settings.storage_bucket_name}/"):
                        return path_part[len(f"{settings.storage_bucket_name}/"):]
            return None
        except Exception:
            return None


# Create service instance
file_upload_service = FileUploadService()
