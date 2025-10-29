from typing import Optional, Dict, Any
from supabase import Client
from app.core.database import get_supabase, get_supabase_admin
from app.models.models import (
    QuestionnaireDetailsCreate, 
    QuestionnaireDetailsUpdate, 
    QuestionnaireDetailsResponse
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class QuestionnaireService:
    def __init__(self):
        self.supabase = get_supabase()
        self.supabase_admin = get_supabase_admin()

    async def create_questionnaire_response(self, questionnaire_data: QuestionnaireDetailsCreate) -> QuestionnaireDetailsResponse:
        """Create a new questionnaire response"""
        try:
            # Check if questionnaire response already exists for this user
            existing_response = await self.get_questionnaire_response_by_user_id(questionnaire_data.user_id)
            if existing_response:
                raise Exception("Questionnaire response already exists for this user")

            # Prepare data for insertion
            questionnaire_dict = questionnaire_data.dict()
            questionnaire_dict.pop("user_id", None)
            
            # Add user_id to the data
            questionnaire_dict["user_id"] = questionnaire_data.user_id

            # Use admin client to avoid RLS blocking parent submissions
            result = self.supabase_admin.table("questionnaire_responses").insert(questionnaire_dict).execute()

            if result.data:
                response_data = result.data[0]
                return self._convert_to_questionnaire_response(response_data)
            else:
                raise Exception("Failed to create questionnaire response")

        except Exception as e:
            logger.error(f"Error creating questionnaire response: {e}")
            raise

    async def get_questionnaire_response_by_user_id(self, user_id: str) -> Optional[QuestionnaireDetailsResponse]:
        """Get questionnaire response by user ID"""
        try:
            result = self.supabase.table("questionnaire_responses").select("*").eq("user_id", user_id).execute()
            
            if result.data:
                return self._convert_to_questionnaire_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error getting questionnaire response: {e}")
            raise

    async def get_questionnaire_response_by_id(self, response_id: str) -> Optional[QuestionnaireDetailsResponse]:
        """Get questionnaire response by ID"""
        try:
            result = self.supabase.table("questionnaire_responses").select("*").eq("id", response_id).execute()
            
            if result.data:
                return self._convert_to_questionnaire_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error getting questionnaire response by ID: {e}")
            raise

    async def update_questionnaire_response(self, user_id: str, update_data: QuestionnaireDetailsUpdate) -> Optional[QuestionnaireDetailsResponse]:
        """Update questionnaire response"""
        try:
            # Convert Pydantic model to dict, excluding None values
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

            if not update_dict:
                return await self.get_questionnaire_response_by_user_id(user_id)

            # Use admin client to avoid RLS blocking updates
            result = self.supabase_admin.table("questionnaire_responses").update(update_dict).eq("user_id", user_id).execute()
            
            if result.data:
                return self._convert_to_questionnaire_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error updating questionnaire response: {e}")
            raise

    async def delete_questionnaire_response(self, user_id: str) -> bool:
        """Delete questionnaire response"""
        try:
            # Use admin client to avoid RLS blocking deletes
            result = self.supabase_admin.table("questionnaire_responses").delete().eq("user_id", user_id).execute()
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error deleting questionnaire response: {e}")
            raise

    async def get_all_questionnaire_responses(self, limit: int = 100, offset: int = 0) -> list[QuestionnaireDetailsResponse]:
        """Get all questionnaire responses with pagination"""
        try:
            result = self.supabase.table("questionnaire_responses").select("*").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            responses = []
            for data in result.data:
                responses.append(self._convert_to_questionnaire_response(data))
            return responses

        except Exception as e:
            logger.error(f"Error getting all questionnaire responses: {e}")
            raise

    async def get_questionnaire_responses_by_country(self, country: str) -> list[QuestionnaireDetailsResponse]:
        """Get questionnaire responses filtered by country"""
        try:
            result = self.supabase.table("questionnaire_responses").select("*").contains("countries_considering", [country]).execute()
            
            responses = []
            for data in result.data:
                responses.append(self._convert_to_questionnaire_response(data))
            return responses

        except Exception as e:
            logger.error(f"Error getting questionnaire responses by country: {e}")
            raise

    async def get_questionnaire_responses_by_education_level(self, education_level: str) -> list[QuestionnaireDetailsResponse]:
        """Get questionnaire responses filtered by education level"""
        try:
            result = self.supabase.table("questionnaire_responses").select("*").eq("education_level", education_level).execute()
            
            responses = []
            for data in result.data:
                responses.append(self._convert_to_questionnaire_response(data))
            return responses

        except Exception as e:
            logger.error(f"Error getting questionnaire responses by education level: {e}")
            raise

    async def get_questionnaire_statistics(self) -> Dict[str, Any]:
        """Get statistics about questionnaire responses"""
        try:
            # Get total responses
            total_result = self.supabase.table("questionnaire_responses").select("id", count="exact").execute()
            total_responses = total_result.count if total_result.count else 0

            # Get responses by education level
            education_levels_result = self.supabase.table("questionnaire_responses").select("education_level").execute()
            education_level_stats = {}
            for response in education_levels_result.data:
                level = response.get("education_level")
                if level:
                    education_level_stats[level] = education_level_stats.get(level, 0) + 1

            # Get responses by year planning
            year_planning_result = self.supabase.table("questionnaire_responses").select("year_planning_abroad").execute()
            year_planning_stats = {}
            for response in year_planning_result.data:
                year = response.get("year_planning_abroad")
                if year:
                    year_planning_stats[year] = year_planning_stats.get(year, 0) + 1

            # Get most common countries
            countries_result = self.supabase.table("questionnaire_responses").select("countries_considering").execute()
            country_stats = {}
            for response in countries_result.data:
                countries = response.get("countries_considering", [])
                for country in countries:
                    country_stats[country] = country_stats.get(country, 0) + 1

            # Get most common target industries
            industries_result = self.supabase.table("questionnaire_responses").select("target_industry").execute()
            industry_stats = {}
            for response in industries_result.data:
                industries = response.get("target_industry", [])
                for industry in industries:
                    industry_stats[industry] = industry_stats.get(industry, 0) + 1

            return {
                "total_responses": total_responses,
                "education_level_distribution": education_level_stats,
                "year_planning_distribution": year_planning_stats,
                "country_distribution": dict(sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
                "industry_distribution": dict(sorted(industry_stats.items(), key=lambda x: x[1], reverse=True)[:10])
            }

        except Exception as e:
            logger.error(f"Error getting questionnaire statistics: {e}")
            raise

    def _convert_to_questionnaire_response(self, data: Dict[str, Any]) -> QuestionnaireDetailsResponse:
        """Convert database row to QuestionnaireResponseResponse"""
        return QuestionnaireDetailsResponse(
            id=data["id"],
            user_id=data["user_id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone_number=data["phone_number"],
            email=data["email"],
            profile_pic_url=data.get("profile_pic_url"),
            ward_full_name=data["ward_full_name"],
            why_study_abroad=data.get("why_study_abroad", []),
            year_planning_abroad=data.get("year_planning_abroad"),
            financial_investment_factor=data.get("financial_investment_factor"),
            finance_education=data.get("finance_education", []),
            current_stage=data.get("current_stage", []),
            research_methods=data.get("research_methods", []),
            countries_considering=data.get("countries_considering", []),
            universities_exploring=data.get("universities_exploring"),
            courses_exploring=data.get("courses_exploring"),
            taken_standardized_tests=data.get("taken_standardized_tests"),
            planning_settle_abroad=data.get("planning_settle_abroad"),
            target_industry=data.get("target_industry", []),
            education_level=data.get("education_level"),
            graduation_university=data.get("graduation_university"),
            graduation_month_year=data.get("graduation_month_year"),
            undergraduate_major=data.get("undergraduate_major"),
            undergraduate_final_grade=data.get("undergraduate_final_grade"),
            concerns_worries=data.get("concerns_worries", []),
            support_exploring_options=data.get("support_exploring_options"),
            support_needed=data.get("support_needed", []),
            how_mentto_help=data.get("how_mentto_help", []),
            how_found_mentto=data.get("how_found_mentto"),
            created_at=datetime.fromisoformat(data["created_at"].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
        )


# Service instance
questionnaire_service = QuestionnaireService()
