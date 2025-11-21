from typing import Optional, Dict, Any, List
from supabase import Client
from app.core.database import get_supabase, get_supabase_admin
from app.models.models import UserCreate, UserResponse, MenteeDetailsCreate, MenteeDetailsUpdate, MenteeDetailsResponse, MentorDetailsCreate, MentorDetailsUpdate, MentorDetailsResponse, MentorshipInterestCreate, MentorshipInterestUpdate, MentorshipInterestResponse, MentorshipInterestStatus, MentorDashboardResponse, ActivityResponse, UpcomingCallResponse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UserService:
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

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user in Supabase"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_firebase_uid(user_data.firebase_uid)
            if existing_user:
                return existing_user

            # Create user in Supabase
            result = self.supabase.table("users").insert({
                "firebase_uid": user_data.firebase_uid,
                "full_name": user_data.full_name,
                "email": user_data.email,
                "role": user_data.role.value
            }).execute()

            if result.data:
                user_data_dict = result.data[0]
                return UserResponse(
                    user_id=user_data_dict["user_id"],
                    full_name=user_data_dict["full_name"],
                    email=user_data_dict["email"],
                    role=user_data_dict["role"],
                    created_at=datetime.fromisoformat(user_data_dict["created_at"].replace('Z', '+00:00')),
                    updated_at=datetime.fromisoformat(user_data_dict["updated_at"].replace('Z', '+00:00'))
                )
            else:
                raise Exception("Failed to create user")

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_firebase_uid(self, firebase_uid: str) -> Optional[UserResponse]:
        """Get user by Firebase UID"""
        try:
            result = self.supabase.table("users").select("*").eq("firebase_uid", firebase_uid).execute()
            
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    user_id=user_data["user_id"],
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    role=user_data["role"],
                    created_at=self._parse_datetime(user_data["created_at"]),
                    updated_at=self._parse_datetime(user_data["updated_at"])
                )
            return None

        except Exception as e:
            logger.error(f"Error getting user by Firebase UID: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by user ID"""
        try:
            result = self.supabase.table("users").select("*").eq("user_id", user_id).execute()
            
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    user_id=user_data["user_id"],
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    role=user_data["role"],
                    created_at=self._parse_datetime(user_data["created_at"]),
                    updated_at=self._parse_datetime(user_data["updated_at"])
                )
            return None

        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            raise

    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get user by email"""
        try:
            result = self.supabase.table("users").select("*").eq("email", email).execute()
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    user_id=user_data["user_id"],
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    role=user_data["role"],
                    created_at=self._parse_datetime(user_data["created_at"]),
                    updated_at=self._parse_datetime(user_data["updated_at"])
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[UserResponse]:
        """Update user information"""
        try:
            result = self.supabase.table("users").update(update_data).eq("user_id", user_id).execute()
            
            if result.data:
                user_data = result.data[0]
                return UserResponse(
                    user_id=user_data["user_id"],
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    role=user_data["role"],
                    created_at=self._parse_datetime(user_data["created_at"]),
                    updated_at=self._parse_datetime(user_data["updated_at"])
                )
            return None

        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise


class MenteeService:
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

    async def create_mentee_details(self, mentee_data: MenteeDetailsCreate) -> MenteeDetailsResponse:
        """Create mentee details"""
        try:
            # Check if mentee details already exist
            existing_details = await self.get_mentee_details_by_user_id(mentee_data.user_id)
            if existing_details:
                raise Exception("Mentee details already exist for this user")

            # Prepare data for insertion
            mentee_dict = mentee_data.dict()
            mentee_dict.pop("user_id", None)
            
            # Add user_id to the data
            mentee_dict["user_id"] = mentee_data.user_id

            result = self.supabase.table("mentee_details").insert(mentee_dict).execute()

            if result.data:
                details_data = result.data[0]
                
                # Send onboarding completion email to mentee
                try:
                    from app.services.email.email_service import email_service
                    user_name = f"{mentee_data.first_name} {mentee_data.last_name}"
                    email_result = email_service.send_mentee_onboarding_email(
                        to_email=mentee_data.email,
                        user_name=user_name
                    )
                    if email_result.get('success'):
                        logger.info(f"Onboarding completion email sent to mentee {mentee_data.email}")
                    else:
                        logger.warning(f"Failed to send onboarding completion email to mentee {mentee_data.email}: {email_result.get('message')}")
                except Exception as email_error:
                    logger.error(f"Error sending onboarding completion email to mentee {mentee_data.email}: {email_error}")
                    # Don't fail the mentee creation if email fails
                
                return self._convert_to_mentee_response(details_data)
            else:
                raise Exception("Failed to create mentee details")

        except Exception as e:
            logger.error(f"Error creating mentee details: {e}")
            raise

    async def get_mentee_details_by_user_id(self, user_id: str) -> Optional[MenteeDetailsResponse]:
        """Get mentee details by user ID"""
        try:
            result = self.supabase.table("mentee_details").select("*").eq("user_id", user_id).execute()
            
            if result.data:
                return self._convert_to_mentee_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error getting mentee details: {e}")
            raise

    async def update_mentee_details(self, user_id: str, update_data: MenteeDetailsUpdate) -> Optional[MenteeDetailsResponse]:
        """Update mentee details"""
        try:
            # Convert Pydantic model to dict, excluding None values
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

            if not update_dict:
                return await self.get_mentee_details_by_user_id(user_id)

            result = self.supabase.table("mentee_details").update(update_dict).eq("user_id", user_id).execute()
            
            if result.data:
                return self._convert_to_mentee_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error updating mentee details: {e}")
            raise

    def _convert_to_mentee_response(self, data: Dict[str, Any]) -> MenteeDetailsResponse:
        """Convert database row to MenteeDetailsResponse"""
        return MenteeDetailsResponse(
            user_id=data["user_id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone_number=data["phone_number"],
            email=data["email"],
            profile_pic_url=data.get("profile_pic_url"),
            why_study_abroad=data.get("why_study_abroad", []),
            intake_applying_for=data.get("intake_applying_for"),
            year_planning_abroad=data.get("year_planning_abroad"),
            finance_education=(data.get("finance_education") or []),
            planning_settle_abroad=data.get("planning_settle_abroad"),
            current_stage=data.get("current_stage", []),
            research_methods=data.get("research_methods", []),
            countries_considering=data.get("countries_considering", []),
            universities_exploring=data.get("universities_exploring", []),
            courses_exploring=data.get("courses_exploring", []),
            taken_standardized_tests=data.get("taken_standardized_tests"),
            standardized_tests_taken=data.get("standardized_tests_taken", []),
            test_scores=data.get("test_scores"),
            taken_english_tests=data.get("taken_english_tests"),
            english_tests_taken=data.get("english_tests_taken", []),
            target_industry=data.get("target_industry", []),
            education_level=data.get("education_level"),
            senior_secondary_school=data.get("senior_secondary_school"),
            educational_board=data.get("educational_board"),
            higher_secondary_stream=data.get("higher_secondary_stream"),
            grade_10_score=data.get("grade_10_score"),
            grade_12_score=data.get("grade_12_score"),
            extracurricular_activities=data.get("extracurricular_activities", []),
            cocurricular_activities=data.get("cocurricular_activities", []),
            current_designation=data.get("current_designation"),
            work_experience_range=data.get("work_experience_range"),
            company_designation_history=data.get("company_designation_history"),
            weather_preference=data.get("weather_preference", []),
            hobbies=data.get("hobbies", []),
            lived_away_from_home=data.get("lived_away_from_home"),
            self_description=data.get("self_description"),
            how_mentto_help=data.get("how_mentto_help", []),
            how_found_mentto=data.get("how_found_mentto"),
            community_referral=data.get("community_referral"),
            graduation_university=data.get("graduation_university"),
            graduation_month_year=data.get("graduation_month_year"),
            undergraduate_major=data.get("undergraduate_major"),
            undergraduate_final_grade=data.get("undergraduate_final_grade"),
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"])
        )


class MentorService:
    def __init__(self):
        self.supabase = get_supabase()
        self.supabase_admin = get_supabase_admin()

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

    async def create_mentor_details(self, mentor_data: MentorDetailsCreate) -> MentorDetailsResponse:
        """Create mentor details"""
        try:
            # Check if mentor details already exist
            existing_details = await self.get_mentor_details_by_user_id(mentor_data.user_id)
            if existing_details:
                raise Exception("Mentor details already exist for this user")

            # Ensure user exists in users table
            user_service = UserService()
            existing_user = await user_service.get_user_by_id(mentor_data.user_id)
            if not existing_user:
                # Create user in users table if they don't exist
                # We'll use the email from mentor_data and create a basic user record
                from app.models.models import UserCreate, UserRole
                user_create_data = UserCreate(
                    firebase_uid=mentor_data.user_id,  # Using user_id as firebase_uid for now
                    full_name=f"{mentor_data.first_name} {mentor_data.last_name}",
                    email=mentor_data.email,
                    role=UserRole.MENTOR
                )
                await user_service.create_user(user_create_data)
                logger.info(f"Created user {mentor_data.user_id} in users table")

            # Prepare data for insertion
            mentor_dict = mentor_data.dict()
            mentor_dict.pop("user_id", None)
            
            # Add user_id, currency, and verification status to the data
            mentor_dict["user_id"] = mentor_data.user_id
            # Use currency from mentor_data if provided, otherwise default to INR
            mentor_dict["currency"] = mentor_data.currency or "INR"
            # Set verification status to pending for new mentor profiles
            mentor_dict["verification_status"] = "pending"

            result = self.supabase.table("mentor_details").insert(mentor_dict).execute()

            if result.data:
                details_data = result.data[0]
                
                # Send verification email to mentor
                try:
                    from app.services.email.email_service import email_service
                    user_name = f"{mentor_data.first_name} {mentor_data.last_name}"
                    email_result = email_service.send_mentor_verification_email(
                        to_email=mentor_data.email,
                        user_name=user_name
                    )
                    if email_result.get('success'):
                        logger.info(f"Verification email sent to mentor {mentor_data.email}")
                    else:
                        logger.warning(f"Failed to send verification email to mentor {mentor_data.email}: {email_result.get('message')}")
                except Exception as email_error:
                    logger.error(f"Error sending verification email to mentor {mentor_data.email}: {email_error}")
                    # Don't fail the mentor creation if email fails
                
                return self._convert_to_mentor_response(details_data)
            else:
                raise Exception("Failed to create mentor details")

        except Exception as e:
            logger.error(f"Error creating mentor details: {e}")
            raise

    async def get_mentor_details_by_user_id(self, user_id: str, include_education: bool = False) -> Optional[MentorDetailsResponse]:
        """Get mentor details by user ID"""
        try:
            result = self.supabase.table("mentor_details").select("*").eq("user_id", user_id).execute()
            
            if result.data:
                mentor_response = self._convert_to_mentor_response(result.data[0])
                
                # Optionally fetch education entries
                if include_education:
                    try:
                        from app.services.user.mentor_education_service import mentor_education_service
                        education_entries = await mentor_education_service.get_education_entries(user_id)
                        mentor_response.education_entries = education_entries
                    except Exception as e:
                        logger.warning(f"Error fetching education entries: {e}")
                        # Don't fail if education fetch fails
                        mentor_response.education_entries = []
                
                return mentor_response
            return None

        except Exception as e:
            logger.error(f"Error getting mentor details: {e}")
            raise

    async def update_mentor_details(self, user_id: str, update_data: MentorDetailsUpdate) -> Optional[MentorDetailsResponse]:
        """Update mentor details"""
        try:
            # Convert Pydantic model to dict, excluding None values
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

            if not update_dict:
                return await self.get_mentor_details_by_user_id(user_id)

            result = self.supabase.table("mentor_details").update(update_dict).eq("user_id", user_id).execute()
            
            if result.data:
                return self._convert_to_mentor_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error updating mentor details: {e}")
            raise

    async def get_mentor_dashboard(self, mentor_id: str) -> MentorDashboardResponse:
        """Get mentor dashboard with total mentees, sessions, earnings, and reviews"""
        try:
            logger.info(f"Getting dashboard data for mentor: {mentor_id}")
            
            # Get mentor details to get hourly rate
            mentor_details = await self.get_mentor_details_by_user_id(mentor_id)
            hourly_rate = mentor_details.mentorship_fee if mentor_details else None
            
            # Get total unique mentees (from accepted mentorship interests)
            mentees_result = self.supabase.table("mentorship_interest").select("mentee_id").eq("mentor_id", mentor_id).eq("status", "accepted").execute()
            unique_mentees = set()
            for interest in mentees_result.data:
                unique_mentees.add(interest["mentee_id"])
            total_mentees = len(unique_mentees)
            
            # Get total sessions and calculate total earnings from actual amounts
            # Only count sessions where payment_status is not "pending" (exclude null and "pending")
            # Use .in_() to explicitly include only "success" and "failed" statuses
            sessions_result = self.supabase.table("sessions").select("id, amount, payment_status").eq("mentor_id", mentor_id).in_("payment_status", ["success", "failed"]).execute()
            
            # Also handle any other non-pending statuses that might exist
            valid_sessions = [s for s in sessions_result.data if s.get("payment_status") and s.get("payment_status") != "pending"]
            total_sessions = len(valid_sessions)
            
            # Calculate total earnings by summing actual amounts from sessions table
            total_earnings = 0.0
            if valid_sessions:
                # Sum all amounts from sessions (handle None values)
                total_earnings = sum(
                    session.get("amount", 0.0) or 0.0 
                    for session in valid_sessions
                )
            
            # Get reviews and calculate average rating
            reviews_result = self.supabase.table("mentor_reviews").select("overall_rating").eq("mentor_id", mentor_id).execute()
            total_reviews = len(reviews_result.data)
            average_rating = None
            
            if total_reviews > 0:
                total_rating = sum(review["overall_rating"] for review in reviews_result.data)
                average_rating = round(total_rating / total_reviews, 2)
            
            # Get recent activities
            recent_activities = await self.get_recent_activities(mentor_id, limit=10)
            
            # Get upcoming calls
            upcoming_calls = await self.get_upcoming_sessions(mentor_id, limit=5)
            upcoming_calls_count = len(upcoming_calls)
            
            logger.info(f"Dashboard data for mentor {mentor_id}: {total_mentees} mentees, {total_sessions} sessions, ${total_earnings} earnings, {average_rating} avg rating, {len(recent_activities)} activities, {upcoming_calls_count} upcoming calls")
            
            return MentorDashboardResponse(
                total_mentees=total_mentees,
                total_sessions=total_sessions,
                total_earnings=total_earnings,
                average_rating=average_rating,
                total_reviews=total_reviews,
                hourly_rate=hourly_rate,
                recent_activities=recent_activities,
                upcoming_calls=upcoming_calls,
                upcoming_calls_count=upcoming_calls_count
            )
            
        except Exception as e:
            logger.error(f"Error getting mentor dashboard: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_recent_activities(self, mentor_id: str, limit: int = 10) -> List[ActivityResponse]:
        """Get recent activities for mentor dashboard"""
        try:
            logger.info(f"Getting recent activities for mentor: {mentor_id}")
            activities = []
            
            # Get recent mentorship interests (pending and accepted)
            interests_result = self.supabase.table("mentorship_interest").select("*, users!mentorship_interest_mentee_id_fkey(full_name)").eq("mentor_id", mentor_id).order("created_at", desc=True).limit(limit).execute()
            
            for interest in interests_result.data:
                mentee_name = interest.get("users", {}).get("full_name", "Unknown")
                activity_type = "interest"
                title = f"{mentee_name} showed interest in your profile"
                description = f"{mentee_name} sent you a mentorship request"
                is_new = interest["status"] == "pending"
                
                activities.append(ActivityResponse(
                    id=f"interest_{interest['id']}",
                    type=activity_type,
                    title=title,
                    description=description,
                    is_new=is_new,
                    created_at=datetime.fromisoformat(interest["created_at"].replace('Z', '+00:00')),
                    user_name=mentee_name,
                    user_id=interest["mentee_id"],
                    metadata={"status": interest["status"], "message": interest.get("message")}
                ))
            
            # Get recent sessions (only where payment_status is not "pending")
            # Use .in_() to explicitly include only "success" and "failed" statuses
            sessions_result = self.supabase.table("sessions").select("*, users!sessions_mentee_id_fkey(full_name)").eq("mentor_id", mentor_id).in_("payment_status", ["success", "failed"]).order("created_at", desc=True).limit(limit).execute()
            
            for session in sessions_result.data:
                # Double-check: skip if payment_status is pending or null
                if not session.get("payment_status") or session.get("payment_status") == "pending":
                    continue
                mentee_name = session.get("users", {}).get("full_name", "Unknown")
                activity_type = "session_confirmed"
                title = f"Call with {mentee_name} confirmed for {session['scheduled_date']} at {session['start_time']}"
                description = f"Session scheduled with {mentee_name}"
                is_new = False  # Sessions are not "new" activities
                
                activities.append(ActivityResponse(
                    id=f"session_{session['id']}",
                    type=activity_type,
                    title=title,
                    description=description,
                    is_new=is_new,
                    created_at=datetime.fromisoformat(session["created_at"].replace('Z', '+00:00')),
                    user_name=mentee_name,
                    user_id=session["mentee_id"],
                    metadata={"scheduled_date": session["scheduled_date"], "start_time": session["start_time"]}
                ))
            
            # Get recent reviews
            reviews_result = self.supabase.table("mentor_reviews").select("*, users!mentor_reviews_mentee_id_fkey(full_name)").eq("mentor_id", mentor_id).order("created_at", desc=True).limit(limit).execute()
            
            for review in reviews_result.data:
                mentee_name = review.get("users", {}).get("full_name", "Unknown")
                rating = review["overall_rating"]
                activity_type = "review"
                title = f"You received a {rating}-star review from {mentee_name}!"
                description = f"Review: {review.get('review_text', 'No comment provided')[:100]}..."
                is_new = False  # Reviews are not "new" activities
                
                activities.append(ActivityResponse(
                    id=f"review_{review['id']}",
                    type=activity_type,
                    title=title,
                    description=description,
                    is_new=is_new,
                    created_at=datetime.fromisoformat(review["created_at"].replace('Z', '+00:00')),
                    user_name=mentee_name,
                    user_id=review["mentee_id"],
                    metadata={"rating": rating, "review_text": review.get("review_text")}
                ))
            
            # Sort all activities by created_at (most recent first) and limit
            activities.sort(key=lambda x: x.created_at, reverse=True)
            activities = activities[:limit]
            
            logger.info(f"Found {len(activities)} recent activities for mentor {mentor_id}")
            return activities
            
        except Exception as e:
            logger.error(f"Error getting recent activities: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_upcoming_sessions(self, mentor_id: str, limit: int = 5) -> List[UpcomingCallResponse]:
        """Get upcoming sessions for mentor dashboard"""
        try:
            logger.info(f"Getting upcoming sessions for mentor: {mentor_id}")
            
            # Get current date and time
            now = datetime.now()
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M:%S")
            
            # Get upcoming sessions (scheduled for today or future dates)
            # Only get sessions where payment_status is not "pending"
            # Use .in_() to explicitly include only "success" and "failed" statuses
            sessions_result = self.supabase.table("sessions").select("*, users!sessions_mentee_id_fkey(full_name)").eq("mentor_id", mentor_id).in_("payment_status", ["success", "failed"]).gte("scheduled_date", current_date).order("scheduled_date", desc=False).order("start_time", desc=False).limit(limit).execute()
            
            upcoming_calls = []
            for session in sessions_result.data:
                # Skip if payment_status is pending or null
                if not session.get("payment_status") or session.get("payment_status") == "pending":
                    continue
                
                # Check if session is in the future
                session_date = session["scheduled_date"]
                session_time = session["start_time"]
                
                # If it's today, check if the time is in the future
                if session_date == current_date:
                    if session_time <= current_time:
                        continue  # Skip past sessions for today
                
                mentee_name = session.get("users", {}).get("full_name", "Unknown")
                
                upcoming_calls.append(UpcomingCallResponse(
                    id=session["id"],
                    mentee_name=mentee_name,
                    mentee_id=session["mentee_id"],
                    scheduled_date=session_date,
                    start_time=session_time,
                    end_time=session["end_time"],
                    session_type=session.get("session_type"),
                    meeting_link=session.get("meeting_link"),
                    notes=session.get("notes"),
                    created_at=datetime.fromisoformat(session["created_at"].replace('Z', '+00:00'))
                ))
            
            logger.info(f"Found {len(upcoming_calls)} upcoming sessions for mentor {mentor_id}")
            return upcoming_calls
            
        except Exception as e:
            logger.error(f"Error getting upcoming sessions: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _convert_to_mentor_response(self, data: Dict[str, Any]) -> MentorDetailsResponse:
        """Convert database row to MentorDetailsResponse"""
        return MentorDetailsResponse(
            user_id=data["user_id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone_number=data["phone_number"],
            email=data["email"],
            profile_pic_url=data.get("profile_pic_url"),
            linkedin=data.get("linkedin"),
            currency=data.get("currency") or "INR",  # Handle None values
            study_country=data["study_country"],
            university_associated=data["university_associated"],
            graduation_date=data.get("graduation_date"),
            university_relationship=data["university_relationship"],
            education_level=data["education_level"],
            course_enrolled=data["course_enrolled"],
            current_grade=data.get("current_grade"),
            current_residence=data["current_residence"],
            taken_standardized_tests=data.get("taken_standardized_tests"),
            standardized_tests_taken=data.get("standardized_tests_taken", []),
            test_scores=data.get("test_scores"),
            taken_english_tests=data.get("taken_english_tests"),
            english_tests_taken=data.get("english_tests_taken", []),
            english_test_scores=data.get("english_test_scores"),
            self_application=data.get("self_application"),
            education_funding=(data.get("education_funding") or []),
            other_universities_admitted=data.get("other_universities_admitted", []),
            work_experience_years=data.get("work_experience_years"),
            current_status=data["current_status"],
            current_designation=data.get("current_designation"),
            industries_worked=data.get("industries_worked", []),
            companies_worked=data.get("companies_worked", []),
            hobbies=data.get("hobbies", []),
            self_description=data["self_description"],
            how_can_help=data.get("how_can_help", []),
            mentorship_fee=data.get("mentorship_fee"),
            previous_mentoring_experience=data.get("previous_mentoring_experience"),
            brief_introduction=data["brief_introduction"],
            mentorship_hours_per_week=data.get("mentorship_hours_per_week"),
            community_referral=data.get("community_referral"),
            verification_status=data.get("verification_status", "pending"),  # Default to pending if not set
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"])
        )


class MentorshipInterestService:
    def __init__(self):
        self.supabase = get_supabase()
        self.supabase_admin = get_supabase_admin()

    async def create_interest(self, interest_data: MentorshipInterestCreate, mentee_id: str) -> MentorshipInterestResponse:
        """Create a mentorship interest"""
        try:
            # Check if interest already exists
            existing = await self.get_interest_by_mentee_mentor(mentee_id, interest_data.mentor_id)
            if existing:
                raise Exception("Interest already exists for this mentor")

            # Verify mentor exists and has mentor role
            mentor = await user_service.get_user_by_id(interest_data.mentor_id)
            if not mentor or mentor.role != "mentor":
                raise Exception("Invalid mentor ID or user is not a mentor")

            # Create interest
            interest_dict = {
                "mentee_id": mentee_id,
                "mentor_id": interest_data.mentor_id,
                "message": interest_data.message,
                "mentee_notes": interest_data.mentee_notes,
                "status": "pending"
            }

            result = self.supabase.table("mentorship_interest").insert(interest_dict).execute()

            if result.data:
                return await self._convert_to_interest_response(result.data[0])
            else:
                raise Exception("Failed to create mentorship interest")

        except Exception as e:
            logger.error(f"Error creating mentorship interest: {e}")
            raise

    async def get_interest_by_mentee_mentor(self, mentee_id: str, mentor_id: str) -> Optional[MentorshipInterestResponse]:
        """Get interest by mentee and mentor IDs"""
        try:
            result = self.supabase.table("mentorship_interest").select("*").eq("mentee_id", mentee_id).eq("mentor_id", mentor_id).execute()
            
            if result.data:
                return await self._convert_to_interest_response(result.data[0])
            return None

        except Exception as e:
            logger.error(f"Error getting mentorship interest: {e}")
            raise

    async def get_interests_by_mentee(self, mentee_id: str) -> List[MentorshipInterestResponse]:
        """Get all interests by a mentee"""
        try:
            result = self.supabase.table("mentorship_interest").select("*").eq("mentee_id", mentee_id).execute()
            
            interests = []
            for data in result.data:
                # Get mentee and mentor details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentor_id"]).execute()
                
                # Get mentee details from mentee_details table
                mentee_details_result = self.supabase.table("mentee_details").select("first_name, last_name, phone_number, email, countries_considering, education_level, why_study_abroad, intake_applying_for, year_planning_abroad, target_industry, self_description").eq("user_id", data["mentee_id"]).execute()
                
                # Get mentor details from mentor_details table (including profile_pic_url)
                mentor_details_result = self.supabase.table("mentor_details").select("first_name, last_name, phone_number, email, profile_pic_url, study_country, university_associated, graduation_date, university_relationship, education_level, course_enrolled, current_grade, current_residence, work_experience_years, current_status, current_designation, industries_worked, companies_worked, hobbies, self_description, how_can_help, mentorship_fee, currency, previous_mentoring_experience, brief_introduction, mentorship_hours_per_week").eq("user_id", data["mentor_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    mentee_data = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                    
                    # Add mentee details if available
                    if mentee_details_result.data:
                        mentee_details = mentee_details_result.data[0]
                        mentee_data.update({
                            "first_name": mentee_details.get("first_name"),
                            "last_name": mentee_details.get("last_name"),
                            "phone_number": mentee_details.get("phone_number"),
                            "countries_considering": mentee_details.get("countries_considering"),
                            "education_level": mentee_details.get("education_level"),
                            "why_study_abroad": mentee_details.get("why_study_abroad"),
                            "intake_applying_for": mentee_details.get("intake_applying_for"),
                            "year_planning_abroad": mentee_details.get("year_planning_abroad"),
                            "target_industry": mentee_details.get("target_industry"),
                            "self_description": mentee_details.get("self_description")
                        })
                    
                    data["mentee"] = mentee_data
                
                if mentor_result.data:
                    mentor_data = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                    
                    # Add mentor details if available
                    if mentor_details_result.data:
                        mentor_details = mentor_details_result.data[0]
                        mentor_data.update({
                            "first_name": mentor_details.get("first_name"),
                            "last_name": mentor_details.get("last_name"),
                            "phone_number": mentor_details.get("phone_number"),
                            "profile_pic_url": mentor_details.get("profile_pic_url"),
                            "study_country": mentor_details.get("study_country"),
                            "university_associated": mentor_details.get("university_associated"),
                            "graduation_date": mentor_details.get("graduation_date"),
                            "university_relationship": mentor_details.get("university_relationship"),
                            "education_level": mentor_details.get("education_level"),
                            "course_enrolled": mentor_details.get("course_enrolled"),
                            "current_grade": mentor_details.get("current_grade"),
                            "current_residence": mentor_details.get("current_residence"),
                            "work_experience_years": mentor_details.get("work_experience_years"),
                            "current_status": mentor_details.get("current_status"),
                            "current_designation": mentor_details.get("current_designation"),
                            "industries_worked": mentor_details.get("industries_worked"),
                            "companies_worked": mentor_details.get("companies_worked"),
                            "hobbies": mentor_details.get("hobbies"),
                            "self_description": mentor_details.get("self_description"),
                            "how_can_help": mentor_details.get("how_can_help"),
                            "mentorship_fee": mentor_details.get("mentorship_fee"),
                            "currency": mentor_details.get("currency"),
                            "previous_mentoring_experience": mentor_details.get("previous_mentoring_experience"),
                            "brief_introduction": mentor_details.get("brief_introduction"),
                            "mentorship_hours_per_week": mentor_details.get("mentorship_hours_per_week")
                        })
                    
                    data["mentor"] = mentor_data
                
                interests.append(await self._convert_to_interest_response(data))
            return interests

        except Exception as e:
            logger.error(f"Error getting mentee interests: {e}")
            raise

    async def get_interests_by_mentee_and_status(self, mentee_id: str, status: str) -> List[MentorshipInterestResponse]:
        """Get mentorship interests for a mentee filtered by status"""
        try:
            result = self.supabase.table("mentorship_interest").select("*").eq("mentee_id", mentee_id).eq("status", status).execute()
            
            interests = []
            for data in result.data:
                # Get mentee and mentor details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentor_id"]).execute()
                
                # Get mentee details from mentee_details table
                mentee_details_result = self.supabase.table("mentee_details").select("first_name, last_name, phone_number, email, countries_considering, education_level, why_study_abroad, intake_applying_for, year_planning_abroad, target_industry, self_description").eq("user_id", data["mentee_id"]).execute()
                
                # Get mentor details from mentor_details table (including profile_pic_url)
                mentor_details_result = self.supabase.table("mentor_details").select("first_name, last_name, phone_number, email, profile_pic_url, study_country, university_associated, graduation_date, university_relationship, education_level, course_enrolled, current_grade, current_residence, work_experience_years, current_status, current_designation, industries_worked, companies_worked, hobbies, self_description, how_can_help, mentorship_fee, currency, previous_mentoring_experience, brief_introduction, mentorship_hours_per_week").eq("user_id", data["mentor_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    mentee_data = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                    
                    # Add mentee details if available
                    if mentee_details_result.data:
                        mentee_details = mentee_details_result.data[0]
                        mentee_data.update({
                            "first_name": mentee_details.get("first_name"),
                            "last_name": mentee_details.get("last_name"),
                            "phone_number": mentee_details.get("phone_number"),
                            "countries_considering": mentee_details.get("countries_considering"),
                            "education_level": mentee_details.get("education_level"),
                            "why_study_abroad": mentee_details.get("why_study_abroad"),
                            "intake_applying_for": mentee_details.get("intake_applying_for"),
                            "year_planning_abroad": mentee_details.get("year_planning_abroad"),
                            "target_industry": mentee_details.get("target_industry"),
                            "self_description": mentee_details.get("self_description")
                        })
                    
                    data["mentee"] = mentee_data
                
                if mentor_result.data:
                    mentor_data = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                    
                    # Add mentor details if available
                    if mentor_details_result.data:
                        mentor_details = mentor_details_result.data[0]
                        mentor_data.update({
                            "first_name": mentor_details.get("first_name"),
                            "last_name": mentor_details.get("last_name"),
                            "phone_number": mentor_details.get("phone_number"),
                            "profile_pic_url": mentor_details.get("profile_pic_url"),
                            "study_country": mentor_details.get("study_country"),
                            "university_associated": mentor_details.get("university_associated"),
                            "graduation_date": mentor_details.get("graduation_date"),
                            "university_relationship": mentor_details.get("university_relationship"),
                            "education_level": mentor_details.get("education_level"),
                            "course_enrolled": mentor_details.get("course_enrolled"),
                            "current_grade": mentor_details.get("current_grade"),
                            "current_residence": mentor_details.get("current_residence"),
                            "work_experience_years": mentor_details.get("work_experience_years"),
                            "current_status": mentor_details.get("current_status"),
                            "current_designation": mentor_details.get("current_designation"),
                            "industries_worked": mentor_details.get("industries_worked"),
                            "companies_worked": mentor_details.get("companies_worked"),
                            "hobbies": mentor_details.get("hobbies"),
                            "self_description": mentor_details.get("self_description"),
                            "how_can_help": mentor_details.get("how_can_help"),
                            "mentorship_fee": mentor_details.get("mentorship_fee"),
                            "currency": mentor_details.get("currency"),
                            "previous_mentoring_experience": mentor_details.get("previous_mentoring_experience"),
                            "brief_introduction": mentor_details.get("brief_introduction"),
                            "mentorship_hours_per_week": mentor_details.get("mentorship_hours_per_week")
                        })
                    
                    data["mentor"] = mentor_data
                
                interests.append(await self._convert_to_interest_response(data))
            return interests

        except Exception as e:
            logger.error(f"Error getting mentee interests by status: {e}")
            raise

    async def get_interests_by_mentor(self, mentor_id: str) -> List[MentorshipInterestResponse]:
        """Get all interests received by a mentor"""
        try:
            logger.info(f"Getting interests for mentor: {mentor_id}")
            
            # Get interests without complex joins first
            result = self.supabase.table("mentorship_interest").select("*").eq("mentor_id", mentor_id).order("created_at", desc=True).execute()
            
            logger.info(f"Found {len(result.data)} interests for mentor {mentor_id}")
            
            interests = []
            for data in result.data:
                # Get mentee and mentor details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentor_id"]).execute()
                
                # Get mentee details from mentee_details table
                mentee_details_result = self.supabase.table("mentee_details").select("first_name, last_name, phone_number, email, countries_considering, education_level, why_study_abroad, intake_applying_for, year_planning_abroad, target_industry, self_description").eq("user_id", data["mentee_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    mentee_data = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                    
                    # Add mentee details if available
                    if mentee_details_result.data:
                        mentee_details = mentee_details_result.data[0]
                        mentee_data.update({
                            "first_name": mentee_details.get("first_name"),
                            "last_name": mentee_details.get("last_name"),
                            "phone_number": mentee_details.get("phone_number"),
                            "countries_considering": mentee_details.get("countries_considering"),
                            "education_level": mentee_details.get("education_level"),
                            "why_study_abroad": mentee_details.get("why_study_abroad"),
                            "intake_applying_for": mentee_details.get("intake_applying_for"),
                            "year_planning_abroad": mentee_details.get("year_planning_abroad"),
                            "target_industry": mentee_details.get("target_industry"),
                            "self_description": mentee_details.get("self_description")
                        })
                    
                    data["mentee"] = mentee_data
                
                if mentor_result.data:
                    data["mentor"] = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                
                interests.append(await self._convert_to_interest_response(data))
            
            logger.info(f"Successfully converted {len(interests)} interests")
            return interests

        except Exception as e:
            logger.error(f"Error getting mentor interests: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_interests_by_mentor_and_status(self, mentor_id: str, status: str) -> List[MentorshipInterestResponse]:
        """Get mentorship interests for a mentor filtered by status"""
        try:
            logger.info(f"Getting {status} interests for mentor: {mentor_id}")
            
            # Get interests without complex joins first
            result = self.supabase.table("mentorship_interest").select("*").eq("mentor_id", mentor_id).eq("status", status).order("created_at", desc=True).execute()
            
            logger.info(f"Found {len(result.data)} {status} interests for mentor {mentor_id}")
            
            interests = []
            for data in result.data:
                # Get mentee and mentor details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentor_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    data["mentee"] = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                
                if mentor_result.data:
                    data["mentor"] = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                
                interests.append(await self._convert_to_interest_response(data))
            
            logger.info(f"Successfully converted {len(interests)} {status} interests")
            return interests

        except Exception as e:
            logger.error(f"Error getting mentor interests by status: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_mentor_mentees(self, mentor_id: str, filter_type: str = "all") -> List[MentorshipInterestResponse]:
        """Get mentor's mentees with filtering (new or all)"""
        try:
            logger.info(f"Getting {filter_type} mentees for mentor: {mentor_id}")
            
            # For "new" filter, get only accepted interests from the last 30 days
            # For "all" filter, get all accepted interests
            if filter_type == "new":
                from datetime import datetime, timedelta
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                result = self.supabase.table("mentorship_interest").select("*").eq("mentor_id", mentor_id).eq("status", "accepted").gte("created_at", thirty_days_ago).order("created_at", desc=True).execute()
            else:
                result = self.supabase.table("mentorship_interest").select("*").eq("mentor_id", mentor_id).eq("status", "accepted").order("created_at", desc=True).execute()
            
            logger.info(f"Found {len(result.data)} {filter_type} mentees for mentor {mentor_id}")
            
            mentees = []
            for data in result.data:
                # Get mentee and mentor details separately
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", data["mentor_id"]).execute()
                
                # Get mentee details from mentee_details table
                mentee_details_result = self.supabase.table("mentee_details").select("first_name, last_name, phone_number, email, countries_considering, education_level, why_study_abroad, intake_applying_for, year_planning_abroad, target_industry, self_description").eq("user_id", data["mentee_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    mentee_data = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                    
                    # Add mentee details if available
                    if mentee_details_result.data:
                        mentee_details = mentee_details_result.data[0]
                        mentee_data.update({
                            "first_name": mentee_details.get("first_name"),
                            "last_name": mentee_details.get("last_name"),
                            "phone_number": mentee_details.get("phone_number"),
                            "countries_considering": mentee_details.get("countries_considering"),
                            "education_level": mentee_details.get("education_level"),
                            "why_study_abroad": mentee_details.get("why_study_abroad"),
                            "intake_applying_for": mentee_details.get("intake_applying_for"),
                            "year_planning_abroad": mentee_details.get("year_planning_abroad"),
                            "target_industry": mentee_details.get("target_industry"),
                            "self_description": mentee_details.get("self_description")
                        })
                    
                    data["mentee"] = mentee_data
                
                if mentor_result.data:
                    data["mentor"] = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                
                mentees.append(await self._convert_to_interest_response(data))
            
            logger.info(f"Successfully converted {len(mentees)} {filter_type} mentees")
            return mentees

        except Exception as e:
            logger.error(f"Error getting {filter_type} mentees for mentor: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def update_interest_status(self, interest_id: str, update_data: MentorshipInterestUpdate, mentor_id: str) -> Optional[MentorshipInterestResponse]:
        """Update interest status (accept/reject)"""
        try:
            # Verify the interest belongs to this mentor
            existing = self.supabase.table("mentorship_interest").select("*").eq("id", interest_id).eq("mentor_id", mentor_id).execute()
            
            if not existing.data:
                raise Exception("Interest not found or not authorized")

            # Update the interest
            update_dict = {
                "status": update_data.status.value,
                "mentor_response": update_data.mentor_response
            }

            result = self.supabase.table("mentorship_interest").update(update_dict).eq("id", interest_id).execute()
            
            if result.data:
                # Get the updated interest data
                updated_data = result.data[0]
                
                # Fetch mentee and mentor details separately (same as other methods)
                mentee_result = self.supabase.table("users").select("full_name, email").eq("user_id", updated_data["mentee_id"]).execute()
                mentor_result = self.supabase.table("users").select("full_name, email").eq("user_id", updated_data["mentor_id"]).execute()
                
                # Get mentee details from mentee_details table
                mentee_details_result = self.supabase.table("mentee_details").select("first_name, last_name, phone_number, email, countries_considering, education_level, why_study_abroad, intake_applying_for, year_planning_abroad, target_industry, self_description").eq("user_id", updated_data["mentee_id"]).execute()
                
                # Add user details to interest data
                if mentee_result.data:
                    mentee_data = {
                        "full_name": mentee_result.data[0]["full_name"],
                        "email": mentee_result.data[0]["email"]
                    }
                    
                    # Add mentee details if available
                    if mentee_details_result.data:
                        mentee_details = mentee_details_result.data[0]
                        mentee_data.update({
                            "first_name": mentee_details.get("first_name"),
                            "last_name": mentee_details.get("last_name"),
                            "phone_number": mentee_details.get("phone_number"),
                            "countries_considering": mentee_details.get("countries_considering"),
                            "education_level": mentee_details.get("education_level"),
                            "why_study_abroad": mentee_details.get("why_study_abroad"),
                            "intake_applying_for": mentee_details.get("intake_applying_for"),
                            "year_planning_abroad": mentee_details.get("year_planning_abroad"),
                            "target_industry": mentee_details.get("target_industry"),
                            "self_description": mentee_details.get("self_description")
                        })
                    
                    updated_data["mentee"] = mentee_data
                
                if mentor_result.data:
                    updated_data["mentor"] = {
                        "full_name": mentor_result.data[0]["full_name"],
                        "email": mentor_result.data[0]["email"]
                    }
                
                return await self._convert_to_interest_response(updated_data)
            return None

        except Exception as e:
            logger.error(f"Error updating interest status: {e}")
            raise

    async def _convert_to_interest_response(self, data: Dict[str, Any]) -> MentorshipInterestResponse:
        """Convert database row to MentorshipInterestResponse"""
        # Handle datetime parsing safely
        created_at = datetime.now()
        updated_at = datetime.now()
        
        if data.get("created_at"):
            try:
                created_at_str = data["created_at"]
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str.replace('Z', '+00:00')
                created_at = datetime.fromisoformat(created_at_str)
            except Exception as e:
                logger.warning(f"Failed to parse created_at '{data.get('created_at')}': {e}")
                created_at = datetime.now()
        
        if data.get("updated_at"):
            try:
                updated_at_str = data["updated_at"]
                if updated_at_str.endswith('Z'):
                    updated_at_str = updated_at_str.replace('Z', '+00:00')
                updated_at = datetime.fromisoformat(updated_at_str)
            except Exception as e:
                logger.warning(f"Failed to parse updated_at '{data.get('updated_at')}': {e}")
                updated_at = datetime.now()
        
        return MentorshipInterestResponse(
            id=data["id"],
            mentee_id=data["mentee_id"],
            mentor_id=data["mentor_id"],
            status=MentorshipInterestStatus(data["status"]),
            message=data.get("message"),
            mentee_notes=data.get("mentee_notes"),
            mentor_response=data.get("mentor_response"),
            created_at=created_at,
            updated_at=updated_at,
            mentee_name=data.get("mentee", {}).get("full_name") if data.get("mentee") else None,
            mentee_email=data.get("mentee", {}).get("email") if data.get("mentee") else None,
            mentor_name=data.get("mentor", {}).get("full_name") if data.get("mentor") else None,
            mentor_email=data.get("mentor", {}).get("email") if data.get("mentor") else None,
            # Additional mentee details
            mentee_first_name=data.get("mentee", {}).get("first_name") if data.get("mentee") else None,
            mentee_last_name=data.get("mentee", {}).get("last_name") if data.get("mentee") else None,
            mentee_phone_number=data.get("mentee", {}).get("phone_number") if data.get("mentee") else None,
            mentee_countries_considering=data.get("mentee", {}).get("countries_considering") if data.get("mentee") else None,
            mentee_education_level=data.get("mentee", {}).get("education_level") if data.get("mentee") else None,
            mentee_why_study_abroad=data.get("mentee", {}).get("why_study_abroad") if data.get("mentee") else None,
            mentee_intake_applying_for=data.get("mentee", {}).get("intake_applying_for") if data.get("mentee") else None,
            mentee_year_planning_abroad=data.get("mentee", {}).get("year_planning_abroad") if data.get("mentee") else None,
            mentee_target_industry=data.get("mentee", {}).get("target_industry") if data.get("mentee") else None,
            mentee_self_description=data.get("mentee", {}).get("self_description") if data.get("mentee") else None,
            # Additional mentor details from mentor onboarding
            mentor_first_name=data.get("mentor", {}).get("first_name") if data.get("mentor") else None,
            mentor_last_name=data.get("mentor", {}).get("last_name") if data.get("mentor") else None,
            mentor_phone_number=data.get("mentor", {}).get("phone_number") if data.get("mentor") else None,
            mentor_study_country=data.get("mentor", {}).get("study_country") if data.get("mentor") else None,
            mentor_university_associated=data.get("mentor", {}).get("university_associated") if data.get("mentor") else None,
            mentor_graduation_date=data.get("mentor", {}).get("graduation_date") if data.get("mentor") else None,
            mentor_university_relationship=data.get("mentor", {}).get("university_relationship") if data.get("mentor") else None,
            mentor_education_level=data.get("mentor", {}).get("education_level") if data.get("mentor") else None,
            mentor_course_enrolled=data.get("mentor", {}).get("course_enrolled") if data.get("mentor") else None,
            mentor_current_grade=data.get("mentor", {}).get("current_grade") if data.get("mentor") else None,
            mentor_current_residence=data.get("mentor", {}).get("current_residence") if data.get("mentor") else None,
            mentor_work_experience_years=data.get("mentor", {}).get("work_experience_years") if data.get("mentor") else None,
            mentor_current_status=data.get("mentor", {}).get("current_status") if data.get("mentor") else None,
            mentor_current_designation=data.get("mentor", {}).get("current_designation") if data.get("mentor") else None,
            mentor_industries_worked=data.get("mentor", {}).get("industries_worked") if data.get("mentor") else None,
            mentor_companies_worked=data.get("mentor", {}).get("companies_worked") if data.get("mentor") else None,
            mentor_hobbies=data.get("mentor", {}).get("hobbies") if data.get("mentor") else None,
            mentor_self_description=data.get("mentor", {}).get("self_description") if data.get("mentor") else None,
            mentor_how_can_help=data.get("mentor", {}).get("how_can_help") if data.get("mentor") else None,
            mentor_mentorship_fee=data.get("mentor", {}).get("mentorship_fee") if data.get("mentor") else None,
            mentor_currency=data.get("mentor", {}).get("currency") if data.get("mentor") else None,
            mentor_previous_mentoring_experience=data.get("mentor", {}).get("previous_mentoring_experience") if data.get("mentor") else None,
            mentor_brief_introduction=data.get("mentor", {}).get("brief_introduction") if data.get("mentor") else None,
            mentor_mentorship_hours_per_week=data.get("mentor", {}).get("mentorship_hours_per_week") if data.get("mentor") else None,
            mentor_profile_pic_url=data.get("mentor", {}).get("profile_pic_url") if data.get("mentor") else None
        )


# Service instances
user_service = UserService()
mentee_service = MenteeService()
mentor_service = MentorService()
mentorship_interest_service = MentorshipInterestService()
