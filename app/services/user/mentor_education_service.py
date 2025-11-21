from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from fastapi import HTTPException, status

from app.core.database import get_supabase
from app.models.models import (
    MentorEducationCreate,
    MentorEducationBulkCreate,
    MentorEducationUpdate,
    MentorEducationResponse
)

logger = logging.getLogger(__name__)


class MentorEducationService:
    def __init__(self):
        self.supabase = get_supabase()

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string from Supabase with robust error handling"""
        try:
            # Handle different datetime formats from Supabase
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str.replace('Z', '+00:00')
            
            # Try to parse with microseconds handling
            if '.' in datetime_str and '+' in datetime_str:
                # Split on the timezone part
                dt_part, tz_part = datetime_str.rsplit('+', 1)
                if '.' in dt_part:
                    # Handle microseconds - normalize to 6 digits
                    base_dt, microsec = dt_part.split('.')
                    if len(microsec) > 6:
                        microsec = microsec[:6]
                    elif len(microsec) < 6:
                        # Pad with zeros to make it 6 digits
                        microsec = microsec.ljust(6, '0')
                    datetime_str = f"{base_dt}.{microsec}+{tz_part}"
            
            return datetime.fromisoformat(datetime_str)
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}': {e}, using current time")
            return datetime.utcnow()

    async def create_education_entry(self, education_data: MentorEducationCreate) -> MentorEducationResponse:
        """Create a new education entry for a mentor"""
        try:
            # Validate mentor exists
            from app.services.user.services import mentor_service
            mentor = await mentor_service.get_mentor_details_by_user_id(education_data.mentor_id)
            if not mentor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mentor not found"
                )

            # If setting as primary, unset other primary entries
            if education_data.is_primary:
                self._unset_other_primary_entries(education_data.mentor_id)

            # Prepare data for insertion
            education_dict = education_data.dict()
            mentor_id = education_dict.pop("mentor_id", None)
            
            education_dict["mentor_id"] = mentor_id
            education_dict["created_at"] = datetime.utcnow().isoformat()
            education_dict["updated_at"] = datetime.utcnow().isoformat()

            result = self.supabase.table("mentor_education").insert(education_dict).execute()

            if result.data:
                entry_data = result.data[0]
                
                # Optionally sync primary to university_associated
                if education_data.is_primary:
                    self._sync_primary_to_mentor_details(education_data.mentor_id, entry_data)
                
                return self._convert_to_education_response(entry_data)
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create education entry"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating education entry: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create education entry: {str(e)}"
            )

    async def create_education_entries_bulk(self, bulk_data: MentorEducationBulkCreate) -> List[MentorEducationResponse]:
        """Create multiple education entries for a mentor in a single transaction"""
        try:
            # Validate mentor exists
            from app.services.user.services import mentor_service
            mentor = await mentor_service.get_mentor_details_by_user_id(bulk_data.mentor_id)
            if not mentor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mentor not found"
                )

            # Check if any entry is marked as primary
            primary_entries = [entry for entry in bulk_data.education_entries if entry.is_primary]
            if len(primary_entries) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only one education entry can be marked as primary"
                )

            # If any entry is primary, unset other primary entries
            if primary_entries:
                self._unset_other_primary_entries(bulk_data.mentor_id)

            # Prepare all entries for bulk insert
            entries_to_insert = []
            for entry in bulk_data.education_entries:
                entry_dict = entry.dict()
                entry_dict["mentor_id"] = bulk_data.mentor_id
                entry_dict["created_at"] = datetime.utcnow().isoformat()
                entry_dict["updated_at"] = datetime.utcnow().isoformat()
                entries_to_insert.append(entry_dict)

            # Bulk insert
            result = self.supabase.table("mentor_education").insert(entries_to_insert).execute()

            if result.data:
                created_entries = []
                primary_entry_data = None
                
                for entry_data in result.data:
                    created_entry = self._convert_to_education_response(entry_data)
                    created_entries.append(created_entry)
                    
                    # Track primary entry for syncing
                    if entry_data.get("is_primary"):
                        primary_entry_data = entry_data

                # Optionally sync primary to university_associated if any entry is primary
                if primary_entry_data:
                    self._sync_primary_to_mentor_details(bulk_data.mentor_id, primary_entry_data)

                logger.info(f"Created {len(created_entries)} education entries for mentor {bulk_data.mentor_id}")
                return created_entries
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create education entries"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating education entries in bulk: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create education entries: {str(e)}"
            )

    async def get_education_entries(self, mentor_id: str, include_legacy: bool = True) -> List[MentorEducationResponse]:
        """Get all education entries for a mentor
        
        Args:
            mentor_id: User ID of the mentor
            include_legacy: If True, also includes education data from mentor_details table
                          if no entries exist in mentor_education (for backward compatibility)
        """
        try:
            # Get entries from new mentor_education table
            result = self.supabase.table("mentor_education").select("*").eq("mentor_id", mentor_id).order("order_index", desc=False).order("graduation_date", desc=True).execute()
            
            entries = []
            for entry_data in result.data:
                entries.append(self._convert_to_education_response(entry_data))
            
            # If no entries found and include_legacy is True, check mentor_details for legacy data
            if len(entries) == 0 and include_legacy:
                legacy_entry = await self._get_legacy_education_entry(mentor_id)
                if legacy_entry:
                    entries.append(legacy_entry)
                    logger.info(f"Found legacy education data for mentor {mentor_id}, consider migrating to mentor_education table")
            
            return entries

        except Exception as e:
            logger.error(f"Error getting education entries: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get education entries"
            )

    async def _get_legacy_education_entry(self, mentor_id: str) -> Optional[MentorEducationResponse]:
        """Get education entry from legacy mentor_details table fields"""
        try:
            result = self.supabase.table("mentor_details").select(
                "user_id, university_associated, study_country, graduation_date, "
                "university_relationship, education_level, course_enrolled, current_grade, created_at, updated_at"
            ).eq("user_id", mentor_id).execute()
            
            if not result.data or len(result.data) == 0:
                return None
            
            mentor_data = result.data[0]
            
            # Only return legacy entry if university_associated exists
            if not mentor_data.get("university_associated"):
                return None
            
            # Create a pseudo-entry from mentor_details
            legacy_entry_dict = {
                "id": f"legacy-{mentor_id}",  # Temporary ID for legacy entries
                "mentor_id": mentor_id,
                "university_name": mentor_data.get("university_associated", ""),
                "country": mentor_data.get("study_country", ""),
                "graduation_date": mentor_data.get("graduation_date"),
                "relationship": mentor_data.get("university_relationship", "alumni"),
                "education_level": mentor_data.get("education_level", ""),
                "course": mentor_data.get("course_enrolled", ""),
                "grade": mentor_data.get("current_grade"),
                "is_primary": True,  # Legacy entries are always considered primary
                "order_index": 0,  # Legacy entries come first
                "created_at": mentor_data.get("created_at", datetime.utcnow().isoformat()),
                "updated_at": mentor_data.get("updated_at", datetime.utcnow().isoformat())
            }
            
            return self._convert_to_education_response(legacy_entry_dict)
            
        except Exception as e:
            logger.warning(f"Error getting legacy education entry for mentor {mentor_id}: {e}")
            return None

    async def get_education_entry(self, education_id: str) -> MentorEducationResponse:
        """Get a specific education entry by ID"""
        try:
            result = self.supabase.table("mentor_education").select("*").eq("id", education_id).execute()
            
            if not result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Education entry not found"
                )
            
            return self._convert_to_education_response(result.data[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting education entry: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get education entry"
            )

    async def update_education_entry(self, education_id: str, update_data: MentorEducationUpdate) -> MentorEducationResponse:
        """Update an education entry"""
        try:
            # Get existing entry to check mentor_id
            existing = await self.get_education_entry(education_id)
            
            # Convert Pydantic model to dict, excluding None values
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            
            if not update_dict:
                return existing

            # If setting as primary, unset other primary entries
            if update_dict.get("is_primary") is True:
                self._unset_other_primary_entries(existing.mentor_id, exclude_id=education_id)

            update_dict["updated_at"] = datetime.utcnow().isoformat()

            result = self.supabase.table("mentor_education").update(update_dict).eq("id", education_id).execute()
            
            if result.data:
                entry_data = result.data[0]
                
                # Optionally sync primary to university_associated
                if update_dict.get("is_primary") is True:
                    self._sync_primary_to_mentor_details(existing.mentor_id, entry_data)
                
                return self._convert_to_education_response(entry_data)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Education entry not found"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating education entry: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update education entry"
            )

    async def delete_education_entry(self, education_id: str) -> bool:
        """Delete an education entry"""
        try:
            # Get existing entry to check if it was primary
            existing = await self.get_education_entry(education_id)
            was_primary = existing.is_primary
            
            result = self.supabase.table("mentor_education").delete().eq("id", education_id).execute()
            
            if result.data:
                # If deleted entry was primary, try to set another as primary
                if was_primary:
                    await self._set_next_primary(existing.mentor_id)
                
                return True
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Education entry not found"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting education entry: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete education entry"
            )

    async def set_primary_education(self, mentor_id: str, education_id: str, sync_to_university_associated: bool = True) -> MentorEducationResponse:
        """Set an education entry as primary and optionally sync to university_associated"""
        try:
            # Get the education entry
            education_entry = await self.get_education_entry(education_id)
            
            # Verify it belongs to the mentor
            if education_entry.mentor_id != mentor_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Education entry does not belong to this mentor"
                )

            # Unset other primary entries
            self._unset_other_primary_entries(mentor_id, exclude_id=education_id)

            # Set this one as primary
            update_data = MentorEducationUpdate(is_primary=True)
            updated_entry = await self.update_education_entry(education_id, update_data)

            # Optionally sync to university_associated
            if sync_to_university_associated:
                self._sync_primary_to_mentor_details(mentor_id, updated_entry.dict())

            return updated_entry

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error setting primary education: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to set primary education"
            )

    def _unset_other_primary_entries(self, mentor_id: str, exclude_id: Optional[str] = None):
        """Unset is_primary flag for all other education entries of a mentor"""
        try:
            query = self.supabase.table("mentor_education").update({"is_primary": False, "updated_at": datetime.utcnow().isoformat()}).eq("mentor_id", mentor_id).eq("is_primary", True)
            
            if exclude_id:
                query = query.neq("id", exclude_id)
            
            query.execute()
        except Exception as e:
            logger.warning(f"Error unsetting other primary entries: {e}")

    def _sync_primary_to_mentor_details(self, mentor_id: str, education_data: Dict[str, Any]):
        """Sync primary education entry to university_associated field in mentor_details"""
        try:
            update_dict = {
                "university_associated": education_data.get("university_name"),
                "study_country": education_data.get("country"),
                "graduation_date": education_data.get("graduation_date"),
                "university_relationship": education_data.get("relationship"),
                "education_level": education_data.get("education_level"),
                "course_enrolled": education_data.get("course"),
                "current_grade": education_data.get("grade"),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Remove None values
            update_dict = {k: v for k, v in update_dict.items() if v is not None}
            
            self.supabase.table("mentor_details").update(update_dict).eq("user_id", mentor_id).execute()
            logger.info(f"Synced primary education to mentor_details for mentor {mentor_id}")
        except Exception as e:
            logger.warning(f"Error syncing primary education to mentor_details: {e}")
            # Don't fail if sync fails, just log warning

    async def _set_next_primary(self, mentor_id: str):
        """Set the next available education entry as primary after deletion"""
        try:
            entries = await self.get_education_entries(mentor_id)
            
            if entries:
                # Set the first one (by order_index or graduation_date) as primary
                first_entry = entries[0]
                await self.set_primary_education(mentor_id, first_entry.id, sync_to_university_associated=True)
        except Exception as e:
            logger.warning(f"Error setting next primary education: {e}")

    def _convert_to_education_response(self, data: Dict[str, Any]) -> MentorEducationResponse:
        """Convert database row to MentorEducationResponse"""
        return MentorEducationResponse(
            id=data["id"],
            mentor_id=data["mentor_id"],
            university_name=data["university_name"],
            country=data["country"],
            graduation_date=data.get("graduation_date"),
            relationship=data["relationship"],
            education_level=data["education_level"],
            course=data["course"],
            grade=data.get("grade"),
            is_primary=data.get("is_primary", False),
            order_index=data.get("order_index"),
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"])
        )


# Create service instance
mentor_education_service = MentorEducationService()

