from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    MENTEE = "mentee"
    MENTOR = "mentor"
    PARENT = "parent"


# Base User Model
class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    role: UserRole


class UserCreate(UserBase):
    firebase_uid: str


class UserResponse(UserBase):
    user_id: str
    timezone: Optional[str] = "UTC"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Mentee Specific Models
class MenteeDetailsBase(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: EmailStr
    profile_pic_url: Optional[str] = None
    why_study_abroad: List[str] = []
    intake_applying_for: Optional[str] = None
    year_planning_abroad: Optional[str] = None
    finance_education: List[str] = []
    planning_settle_abroad: Optional[bool] = None
    current_stage: List[str] = []
    research_methods: List[str] = []
    countries_considering: List[str] = []
    universities_exploring: List[str] = []
    courses_exploring: List[str] = []
    taken_standardized_tests: Optional[bool] = None
    standardized_tests_taken: List[str] = []
    test_scores: Optional[Dict[str, Any]] = None
    taken_english_tests: Optional[bool] = None
    english_tests_taken: List[str] = []
    target_industry: List[str] = []
    education_level: Optional[str] = None
    senior_secondary_school: Optional[str] = None
    educational_board: Optional[str] = None
    higher_secondary_stream: Optional[str] = None
    grade_10_score: Optional[float] = None
    grade_12_score: Optional[float] = None
    extracurricular_activities: List[str] = []
    cocurricular_activities: List[str] = []
    weather_preference: List[str] = []
    hobbies: List[str] = []
    # Career/Professional details (replacing Achievements step)
    current_designation: Optional[str] = None
    work_experience_range: Optional[str] = None
    company_designation_history: Optional[str] = None
    lived_away_from_home: Optional[bool] = None
    self_description: Optional[str] = None
    how_mentto_help: List[str] = []
    how_found_mentto: Optional[str] = None
    community_referral: Optional[bool] = None
    # Undergraduate education details
    graduation_university: Optional[str] = None
    graduation_month_year: Optional[str] = None  # e.g., "June 2023"
    undergraduate_major: Optional[str] = None
    undergraduate_final_grade: Optional[str] = None


class MenteeDetailsCreate(MenteeDetailsBase):
    user_id: str


class MenteeDetailsUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_pic_url: Optional[str] = None
    why_study_abroad: Optional[List[str]] = None
    intake_applying_for: Optional[str] = None
    year_planning_abroad: Optional[str] = None
    finance_education: Optional[List[str]] = None
    planning_settle_abroad: Optional[bool] = None
    current_stage: Optional[List[str]] = None
    research_methods: Optional[List[str]] = None
    countries_considering: Optional[List[str]] = None
    universities_exploring: Optional[List[str]] = None
    courses_exploring: Optional[List[str]] = None
    taken_standardized_tests: Optional[bool] = None
    standardized_tests_taken: Optional[List[str]] = None
    test_scores: Optional[Dict[str, Any]] = None
    taken_english_tests: Optional[bool] = None
    english_tests_taken: Optional[List[str]] = None
    target_industry: Optional[List[str]] = None
    education_level: Optional[str] = None
    senior_secondary_school: Optional[str] = None
    educational_board: Optional[str] = None
    higher_secondary_stream: Optional[str] = None
    grade_10_score: Optional[float] = None
    grade_12_score: Optional[float] = None
    extracurricular_activities: Optional[List[str]] = None
    cocurricular_activities: Optional[List[str]] = None
    weather_preference: Optional[List[str]] = None
    hobbies: Optional[List[str]] = None
    # Career/Professional details (replacing Achievements step)
    current_designation: Optional[str] = None
    work_experience_range: Optional[str] = None
    company_designation_history: Optional[str] = None
    lived_away_from_home: Optional[bool] = None
    self_description: Optional[str] = None
    how_mentto_help: Optional[List[str]] = None
    how_found_mentto: Optional[str] = None
    community_referral: Optional[bool] = None
    # Undergraduate education details (updates)
    graduation_university: Optional[str] = None
    graduation_month_year: Optional[str] = None
    undergraduate_major: Optional[str] = None
    undergraduate_final_grade: Optional[str] = None


class MenteeDetailsResponse(MenteeDetailsBase):
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Mentor Specific Models
class MentorDetailsBase(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: EmailStr
    profile_pic_url: Optional[str] = None
    linkedin: Optional[str] = None
    study_country: str
    university_associated: str
    graduation_date: Optional[str] = None
    university_relationship: str
    education_level: str
    course_enrolled: str
    current_grade: Optional[str] = None
    current_residence: str
    taken_standardized_tests: Optional[bool] = None
    standardized_tests_taken: List[str] = []
    test_scores: Optional[Dict[str, Any]] = None
    taken_english_tests: Optional[bool] = None
    english_tests_taken: List[str] = []
    english_test_scores: Optional[Dict[str, Any]] = None
    self_application: Optional[bool] = None
    education_funding: List[str]
    other_universities_admitted: List[str] = []
    work_experience_years: Optional[int] = None
    current_status: str
    current_designation: Optional[str] = None
    industries_worked: List[str] = []
    companies_worked: List[str] = []
    hobbies: List[str] = []
    self_description: str
    how_can_help: List[str] = []
    mentorship_fee: Optional[float] = None
    currency: Optional[str] = "INR"
    previous_mentoring_experience: Optional[bool] = None
    brief_introduction: str
    mentorship_hours_per_week: Optional[int] = None
    community_referral: Optional[bool] = None


class MentorDetailsCreate(MentorDetailsBase):
    user_id: str


class MentorDetailsUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_pic_url: Optional[str] = None
    linkedin: Optional[str] = None
    study_country: Optional[str] = None
    university_associated: Optional[str] = None
    graduation_date: Optional[str] = None
    university_relationship: Optional[str] = None
    education_level: Optional[str] = None
    course_enrolled: Optional[str] = None
    current_grade: Optional[str] = None
    current_residence: Optional[str] = None
    taken_standardized_tests: Optional[bool] = None
    standardized_tests_taken: Optional[List[str]] = None
    test_scores: Optional[Dict[str, Any]] = None
    taken_english_tests: Optional[bool] = None
    english_tests_taken: Optional[List[str]] = None
    english_test_scores: Optional[Dict[str, Any]] = None
    self_application: Optional[bool] = None
    education_funding: Optional[List[str]] = None
    other_universities_admitted: Optional[List[str]] = None
    work_experience_years: Optional[int] = None
    current_status: Optional[str] = None
    current_designation: Optional[str] = None
    industries_worked: Optional[List[str]] = None
    companies_worked: Optional[List[str]] = None
    hobbies: Optional[List[str]] = None
    self_description: Optional[str] = None
    how_can_help: Optional[List[str]] = None
    mentorship_fee: Optional[float] = None
    previous_mentoring_experience: Optional[bool] = None
    brief_introduction: Optional[str] = None
    mentorship_hours_per_week: Optional[int] = None
    community_referral: Optional[bool] = None


# Mentor Education Models (for storing multiple education entries including abroad universities)
class MentorEducationBase(BaseModel):
    university_name: str = Field(..., description="Name of the university/institution")
    country: str = Field(..., description="Country where the university is located")
    graduation_date: Optional[str] = Field(None, description="Graduation date (e.g., 'May 2020' or '2020')")
    relationship: str = Field(..., description="Relationship with university: 'current', 'alumni',  etc.")
    education_level: str = Field(..., description="Education level: 'bachelor', 'master', 'phd', 'diploma', etc.")
    course: str = Field(..., description="Course/Major/Degree name")
    grade: Optional[str] = Field(None, description="Final grade or GPA")
    is_primary: bool = Field(default=False, description="Whether this is the primary/current education for mentoring")
    order_index: Optional[int] = Field(None, description="Order for sorting (lower number = higher priority)")


class MentorEducationCreate(MentorEducationBase):
    mentor_id: str = Field(..., description="ID of the mentor this education belongs to")


class MentorEducationBulkCreate(BaseModel):
    mentor_id: str = Field(..., description="ID of the mentor these education entries belong to")
    education_entries: List[MentorEducationBase] = Field(..., min_items=1, description="List of education entries to create")


class MentorEducationUpdate(BaseModel):
    university_name: Optional[str] = None
    country: Optional[str] = None
    graduation_date: Optional[str] = None
    relationship: Optional[str] = None
    education_level: Optional[str] = None
    course: Optional[str] = None
    grade: Optional[str] = None
    is_primary: Optional[bool] = None
    order_index: Optional[int] = None


class MentorEducationResponse(MentorEducationBase):
    id: str
    mentor_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MentorDetailsResponse(MentorDetailsBase):
    user_id: str
    currency: str = "INR"
    verification_status: Optional[str] = "pending"  # pending, verified, rejected
    created_at: datetime
    updated_at: datetime
    education_entries: Optional[List[MentorEducationResponse]] = None  # All education entries including abroad universities

    class Config:
        from_attributes = True


# Admin Account Models
class AdminAccountBase(BaseModel):
    user_id: str
    email: EmailStr
    is_active: bool = True

class AdminAccountCreate(AdminAccountBase):
    pass

class AdminAccountResponse(AdminAccountBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Mentor Verification Models
class MentorVerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class MentorVerificationUpdate(BaseModel):
    verification_status: MentorVerificationStatus
    admin_notes: Optional[str] = None

# Mentorship Interest Models
class MentorshipInterestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# Email Logging Models
class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class EmailLogBase(BaseModel):
    recipient_email: EmailStr
    subject: str
    email_type: str  # e.g., "mentor_verification", "mentor_verified", "onboarding"
    status: EmailStatus
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmailLogCreate(EmailLogBase):
    pass


class EmailLogResponse(EmailLogBase):
    id: str
    updated_at: datetime

    class Config:
        from_attributes = True


class MentorshipInterestCreate(BaseModel):
    mentor_id: str
    message: Optional[str] = None
    mentee_notes: Optional[str] = None


class MentorshipInterestUpdate(BaseModel):
    status: MentorshipInterestStatus
    mentor_response: Optional[str] = None


class MentorshipInterestResponse(BaseModel):
    id: str
    mentee_id: str
    mentor_id: str
    status: MentorshipInterestStatus
    message: Optional[str] = None
    mentee_notes: Optional[str] = None
    mentor_response: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include user details for better API responses
    mentee_name: Optional[str] = None
    mentee_email: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_email: Optional[str] = None
    
    # Additional mentee details
    mentee_first_name: Optional[str] = None
    mentee_last_name: Optional[str] = None
    mentee_phone_number: Optional[str] = None
    mentee_countries_considering: Optional[List[str]] = None
    mentee_education_level: Optional[str] = None
    mentee_why_study_abroad: Optional[List[str]] = None
    mentee_intake_applying_for: Optional[str] = None
    mentee_year_planning_abroad: Optional[str] = None
    mentee_target_industry: Optional[List[str]] = None
    mentee_self_description: Optional[str] = None
    
    # Additional mentor details from mentor onboarding
    mentor_first_name: Optional[str] = None
    mentor_last_name: Optional[str] = None
    mentor_phone_number: Optional[str] = None
    mentor_study_country: Optional[str] = None
    mentor_university_associated: Optional[str] = None
    mentor_graduation_date: Optional[str] = None
    mentor_university_relationship: Optional[str] = None
    mentor_education_level: Optional[str] = None
    mentor_course_enrolled: Optional[str] = None
    mentor_current_grade: Optional[str] = None
    mentor_current_residence: Optional[str] = None
    mentor_work_experience_years: Optional[int] = None
    mentor_current_status: Optional[str] = None
    mentor_current_designation: Optional[str] = None
    mentor_industries_worked: Optional[List[str]] = None
    mentor_companies_worked: Optional[List[str]] = None
    mentor_hobbies: Optional[List[str]] = None
    mentor_self_description: Optional[str] = None
    mentor_how_can_help: Optional[List[str]] = None
    mentor_mentorship_fee: Optional[float] = None
    mentor_currency: Optional[str] = None
    mentor_previous_mentoring_experience: Optional[bool] = None
    mentor_brief_introduction: Optional[str] = None
    mentor_mentorship_hours_per_week: Optional[int] = None
    # Additional media
    mentor_profile_pic_url: Optional[str] = None

    class Config:
        from_attributes = True


class ActivityResponse(BaseModel):
    id: str
    type: str  # "interest", "session_confirmed", "review", "reschedule", etc.
    title: str
    description: str
    is_new: bool = False
    created_at: datetime
    user_name: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional data like session time, rating, etc.

    class Config:
        from_attributes = True


class UpcomingCallResponse(BaseModel):
    id: str
    mentee_name: str
    mentee_id: str
    scheduled_date: str
    start_time: str
    end_time: str
    session_type: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MentorDashboardResponse(BaseModel):
    total_mentees: int
    total_sessions: int
    total_earnings: float
    average_rating: Optional[float] = None
    total_reviews: int
    hourly_rate: Optional[float] = None
    recent_activities: List[ActivityResponse] = []
    upcoming_calls: List[UpcomingCallResponse] = []
    upcoming_calls_count: int = 0

    class Config:
        from_attributes = True


# Authentication Models
class FirebaseTokenRequest(BaseModel):
    firebase_token: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    firebase_uid: Optional[str] = None


class EmailPasswordSignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.MENTEE


class EmailPasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    continueUrl: Optional[str] = None  # Optional redirect URL after password reset


# Google Calendar Models
class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendee_emails: List[str] = []
    location: Optional[str] = None
    meeting_link: Optional[str] = None


class CalendarEventResponse(BaseModel):
    event_id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendee_emails: List[str] = []
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: str  # confirmed, tentative, cancelled
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilitySlot(BaseModel):
    start_time: datetime
    end_time: datetime
    is_available: bool
    event_title: Optional[str] = None


class CalendarSyncResponse(BaseModel):
    success: bool
    message: str
    events_synced: int
    last_sync: datetime


class SendInvitationRequest(BaseModel):
    mentee_email: str
    event_title: str
    event_description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None


# Mentor Suggestion Models
class MentorSuggestionRequest(BaseModel):
    limit: Optional[int] = 10
    min_match_score: Optional[float] = 0.3


class MentorSuggestionResponse(BaseModel):
    mentor_id: str
    mentor_name: str
    mentor_email: str
    match_score: float
    match_reasons: List[str]
    mentor_details: MentorDetailsResponse
    user_details: UserResponse
    
    class Config:
        from_attributes = True


# WebSocket Chat Models
class ChatMessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"

class ChatMessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class ChatMessageCreate(BaseModel):
    recipient_id: str
    message_type: ChatMessageType = ChatMessageType.TEXT
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatMessageResponse(BaseModel):
    id: str
    sender_id: str
    recipient_id: str
    message_type: ChatMessageType
    content: str
    status: ChatMessageStatus
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    # Include sender details for better API responses
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None

    class Config:
        from_attributes = True

class WebSocketMessage(BaseModel):
    type: str  # "message", "typing", "read", "join", "leave"
    data: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()

class ChatConversationResponse(BaseModel):
    conversation_id: str
    participant_id: str
    participant_name: str
    participant_email: str
    last_message: Optional[ChatMessageResponse] = None
    unread_count: int = 0
    last_activity: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# Notification Models
class NotificationType(str, Enum):
    MESSAGE = "message"
    MENTORSHIP_INTEREST = "mentorship_interest"
    MENTORSHIP_ACCEPTED = "mentorship_accepted"
    MENTORSHIP_REJECTED = "mentorship_rejected"
    CALENDAR_INVITATION = "calendar_invitation"
    MENTOR_SUGGESTION = "mentor_suggestion"
    SYSTEM = "system"
    REMINDER = "reminder"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

class NotificationCreate(BaseModel):
    recipient_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None
    expires_at: Optional[datetime] = None

class NotificationUpdate(BaseModel):
    status: Optional[NotificationStatus] = None
    read_at: Optional[datetime] = None

class NotificationResponse(BaseModel):
    id: str
    recipient_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    status: NotificationStatus
    metadata: Optional[Dict[str, Any]] = None
    action_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    read_at: Optional[datetime] = None
    
    # Include sender details for better API responses
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None

    class Config:
        from_attributes = True

class NotificationSummary(BaseModel):
    total_unread: int
    unread_by_type: Dict[str, int]
    recent_notifications: List[NotificationResponse]

class BulkNotificationUpdate(BaseModel):
    notification_ids: List[str]
    status: NotificationStatus


# Response Models
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None


# Mentor Review Models
class SessionQuality(str, Enum):
    HELPFUL = "Helpful"
    KNOWLEDGEABLE = "Knowledgeable"
    SUPPORTIVE = "Supportive"
    PROFESSIONAL = "Professional"

class MentorReviewCreate(BaseModel):
    mentor_id: str
    mentorship_interest_id: Optional[str] = None  # Optional link to specific mentorship session
    overall_rating: int = Field(..., ge=1, le=5, description="Overall rating from 1-5")
    session_qualities: List[SessionQuality] = Field(..., description="What made this session great?")
    review_text: Optional[str] = Field(None, max_length=1000, description="Write a Review")

class MentorReviewUpdate(BaseModel):
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    session_qualities: Optional[List[SessionQuality]] = None
    review_text: Optional[str] = Field(None, max_length=1000)

class MentorReviewResponse(BaseModel):
    id: str
    mentee_id: str
    mentor_id: str
    mentorship_interest_id: Optional[str] = None
    overall_rating: int
    session_qualities: List[str]
    review_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include mentee details for better API responses
    mentee_name: Optional[str] = None
    mentee_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class MentorReviewSummary(BaseModel):
    mentor_id: str
    total_reviews: int
    average_rating: float
    rating_distribution: Dict[str, int]  # {"1": 0, "2": 1, "3": 2, "4": 5, "5": 10}
    quality_counts: Dict[str, int]  # {"Helpful": 15, "Knowledgeable": 12, ...}
    recent_reviews: List[MentorReviewResponse]


# Conversation Models
class ConversationMessage(BaseModel):
    id: str
    sender_id: str
    recipient_id: str
    message_type: str
    content: str
    status: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    # Include sender details
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class ConversationSummary(BaseModel):
    mentor_id: str
    mentor_name: str
    mentor_email: str
    mentorship_interest_id: str
    last_message: Optional[ConversationMessage] = None
    unread_count: int = 0
    total_messages: int = 0
    last_activity: Optional[datetime] = None
    is_online: bool = False  # Could be extended with real-time status
    
    class Config:
        from_attributes = True


# Session Models
class CallType(str, Enum):
    VIDEO_CALL = "video_call"
    PHONE_CALL = "phone_call"
    IN_PERSON = "in_person"
    CHAT = "chat"

class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"

class SessionCreate(BaseModel):
    other_user_id: str = Field(..., description="ID of the other user (mentor_id if mentee is scheduling, mentee_id if mentor is scheduling)")
    mentorship_interest_id: Optional[str] = None
    call_type: CallType
    scheduled_date: str = Field(..., description="Date in YYYY-MM-DD format")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")
    timezone: str = Field(default="UTC", description="Timezone for the session")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes for the session")

class SessionUpdate(BaseModel):
    call_type: Optional[CallType] = None
    scheduled_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    start_time: Optional[str] = Field(None, description="Start time in HH:MM format (24-hour)")
    end_time: Optional[str] = Field(None, description="End time in HH:MM format (24-hour)")
    timezone: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    status: Optional[SessionStatus] = None
    meeting_link: Optional[str] = Field(None, max_length=500)
    meeting_id: Optional[str] = Field(None, max_length=100)

class SessionResponse(BaseModel):
    id: str
    mentee_id: str
    mentor_id: str
    mentorship_interest_id: Optional[str] = None
    call_type: str
    scheduled_date: str
    start_time: str
    end_time: str
    timezone: str
    notes: Optional[str] = None
    status: str
    meeting_link: Optional[str] = None
    meeting_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include user details for better API responses
    mentee_name: Optional[str] = None
    mentee_email: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_email: Optional[str] = None
    
    # Payment information
    payment_id: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = None
    payment_status: Optional[str] = "pending"  # pending, success, failed
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    
    # Scheduled calls information
    scheduled_call_id: Optional[str] = None
    scheduled_call_status: Optional[str] = None
    scheduled_call_title: Optional[str] = None
    scheduled_call_description: Optional[str] = None
    
    # Session scheduling information
    scheduled_by_user_id: Optional[str] = None  # User ID of who initiated the session
    invited_by_user_id: Optional[str] = None    # User ID of who was invited to the session
    
    class Config:
        from_attributes = True

class SessionSummary(BaseModel):
    total_sessions: int
    upcoming_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    next_session: Optional[SessionResponse] = None
    recent_sessions: List[SessionResponse] = []

class AllSessionsResponse(BaseModel):
    upcoming_sessions: List[SessionResponse]
    past_sessions: List[SessionResponse]
    total_upcoming: int
    total_past: int
    total_sessions: int


# Questionnaire Models (Parent/Guardian Form)
class QuestionnaireDetailsBase(BaseModel):
    # Step 1: Basic Information
    first_name: str
    last_name: str
    phone_number: str
    email: EmailStr
    profile_pic_url: Optional[str] = None
    
    # Step 2: Ward's Information
    ward_full_name: str
    
    # Step 3: Why study abroad (multiple choice, ranked)
    why_study_abroad: List[str] = []
    
    # Step 4: Year planning to send abroad
    year_planning_abroad: Optional[str] = None
    
    # Step 5: Financial investment consideration
    financial_investment_factor: Optional[bool] = None
    
    # Step 6: How to finance education (multiple choice)
    finance_education: List[str] = []
    
    # Step 7: Current stage in study abroad journey (multiple choice)
    current_stage: List[str] = []
    
    # Step 8: Research methods (multiple choice)
    research_methods: List[str] = []
    
    # Step 9: Countries considering (multiple choice)
    countries_considering: List[str] = []
    
    # Step 10: Universities exploring
    universities_exploring: Optional[str] = None
    
    # Step 11: Courses exploring
    courses_exploring: Optional[str] = None
    
    # Step 12: Taken standardized tests
    taken_standardized_tests: Optional[bool] = None
    
    # Step 13: Planning to settle abroad
    planning_settle_abroad: Optional[str] = None
    
    # Step 14: Target industry (multiple choice)
    target_industry: List[str] = []
    
    # Step 15: Education level
    education_level: Optional[str] = None
    
    # Step 16: Concerns/worries (multiple choice)
    concerns_worries: List[str] = []
    
    # Step 17: Support for exploring options
    support_exploring_options: Optional[str] = None
    
    # Step 18: Kind of support needed (multiple choice)
    support_needed: List[str] = []
    
    # Step 19: How Mentto can help (multiple choice)
    how_mentto_help: List[str] = []
    
    # Step 20: How found Mentto
    how_found_mentto: Optional[str] = None
    
    # Ward's Undergraduate Education Details
    graduation_university: Optional[str] = None
    graduation_month_year: Optional[str] = None  # e.g., "June 2023"
    undergraduate_major: Optional[str] = None
    undergraduate_final_grade: Optional[str] = None


class QuestionnaireDetailsCreate(QuestionnaireDetailsBase):
    user_id: str


class QuestionnaireDetailsUpdate(BaseModel):
    # Step 1: Basic Information
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
    # Step 2: Ward's Information
    ward_full_name: Optional[str] = None
    
    # Step 3: Why study abroad (multiple choice, ranked)
    why_study_abroad: Optional[List[str]] = None
    
    # Step 4: Year planning to send abroad
    year_planning_abroad: Optional[str] = None
    
    # Step 5: Financial investment consideration
    financial_investment_factor: Optional[bool] = None
    
    # Step 6: How to finance education (multiple choice)
    finance_education: Optional[List[str]] = None
    
    # Step 7: Current stage in study abroad journey (multiple choice)
    current_stage: Optional[List[str]] = None
    
    # Step 8: Research methods (multiple choice)
    research_methods: Optional[List[str]] = None
    
    # Step 9: Countries considering (multiple choice)
    countries_considering: Optional[List[str]] = None
    
    # Step 10: Universities exploring
    universities_exploring: Optional[str] = None
    
    # Step 11: Courses exploring
    courses_exploring: Optional[str] = None
    
    # Step 12: Taken standardized tests
    taken_standardized_tests: Optional[bool] = None
    
    # Step 13: Planning to settle abroad
    planning_settle_abroad: Optional[str] = None
    
    # Step 14: Target industry (multiple choice)
    target_industry: Optional[List[str]] = None
    
    # Step 15: Education level
    education_level: Optional[str] = None
    
    # Step 16: Concerns/worries (multiple choice)
    concerns_worries: Optional[List[str]] = None
    
    # Step 17: Support for exploring options
    support_exploring_options: Optional[str] = None
    
    # Step 18: Kind of support needed (multiple choice)
    support_needed: Optional[List[str]] = None
    
    # Step 19: How Mentto can help (multiple choice)
    how_mentto_help: Optional[List[str]] = None
    
    # Step 20: How found Mentto
    how_found_mentto: Optional[str] = None
    
    # Ward's Undergraduate Education Details (updates)
    graduation_university: Optional[str] = None
    graduation_month_year: Optional[str] = None
    undergraduate_major: Optional[str] = None
    undergraduate_final_grade: Optional[str] = None


class QuestionnaireDetailsResponse(QuestionnaireDetailsBase):
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Payment Models
class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class PaymentMethod(str, Enum):
    CARD = "card"
    NET_BANKING = "netbanking"
    UPI = "upi"
    WALLET = "wallet"
    EMI = "emi"
    CASH = "cash"

class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in INR")
    currency: str = Field(default="INR", description="Currency code")
    mentor_id: str = Field(..., description="ID of the mentor being paid")
    session_id: Optional[str] = Field(None, description="ID of the session if payment is for a specific session")
    description: Optional[str] = Field(None, description="Payment description")
    notes: Optional[Dict[str, Any]] = Field(None, description="Additional notes or metadata")

class PaymentResponse(BaseModel):
    id: str
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount: float
    currency: str
    status: PaymentStatus
    payment_method: Optional[PaymentMethod] = None
    mentee_id: str
    mentor_id: str
    session_id: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None
    razorpay_signature: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Include user details for better API responses
    mentee_name: Optional[str] = None
    mentee_email: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_email: Optional[str] = None

    class Config:
        from_attributes = True

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    payment_method: Optional[PaymentMethod] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None

class PaymentVerificationRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

class RefundCreate(BaseModel):
    payment_id: str
    amount: Optional[float] = Field(None, description="Refund amount (if not provided, full amount will be refunded)")
    notes: Optional[str] = Field(None, description="Refund reason or notes")

class RefundResponse(BaseModel):
    id: str
    payment_id: str
    razorpay_refund_id: str
    amount: float
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentSummary(BaseModel):
    total_payments: int
    total_amount: float
    successful_payments: int
    failed_payments: int
    pending_payments: int
    total_refunds: float
    net_amount: float

class WebhookEvent(BaseModel):
    event: str
    account_id: str
    contains: List[str]
    created_at: int
    payload: Dict[str, Any]

class PaymentWebhookData(BaseModel):
    entity: str
    account_id: str
    event: str
    contains: List[str]
    payload: Dict[str, Any]
    created_at: int


# Calendar Events and Slots Models
class CalendarEventType(str, Enum):
    FREE = "free"
    BLOCKED = "blocked"
    BUSY = "busy"

class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    event_type: CalendarEventType = CalendarEventType.BUSY
    is_all_day: bool = False
    attendees: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    is_available: bool
    event_title: Optional[str] = None
    event_type: CalendarEventType = CalendarEventType.FREE

class CalendarEventsResponse(BaseModel):
    events: List[CalendarEvent]
    free_slots: List[TimeSlot]
    blocked_slots: List[TimeSlot]
    total_events: int
    total_free_slots: int
    total_blocked_slots: int
    date_range: Dict[str, str]  # {"start": "2024-01-01", "end": "2024-01-31"}

class CalendarSyncRequest(BaseModel):
    email: str
    start_date: Optional[str] = None  # YYYY-MM-DD format
    end_date: Optional[str] = None    # YYYY-MM-DD format
    include_free_slots: bool = True
    include_blocked_slots: bool = True

class BatchFreeSlotsRequest(BaseModel):
    mentor_emails: List[str]
    start_date: Optional[str] = None  # YYYY-MM-DD format
    end_date: Optional[str] = None    # YYYY-MM-DD format
    duration_minutes: int = 60
    timezone: str = "UTC"

class MentorAvailability(BaseModel):
    mentor_email: str
    mentor_name: Optional[str] = None
    mentor_id: Optional[str] = None
    free_slots: List[TimeSlot]
    total_free_slots: int

class CommonSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    available_mentors: List[str]
    available_mentor_count: int

class BatchFreeSlotsResponse(BaseModel):
    mentors_availability: List[MentorAvailability]
    common_slots: List[CommonSlot]
    total_mentors: int
    total_common_slots: int
    date_range: Dict[str, str]
    requested_duration_minutes: int

class ScheduleCallRequest(BaseModel):
    mentor_email: str
    start_time: datetime
    end_time: datetime
    title: str
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None

class PendingCallRequest(BaseModel):
    mentor_email: str
    start_time: datetime
    end_time: datetime
    title: str
    description: Optional[str] = None
    notes: Optional[str] = None
    amount: float
    currency: str = "INR"

class PaymentVerificationRequest(BaseModel):
    call_id: str
    payment_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class ScheduledCall(BaseModel):
    id: str
    mentee_id: str
    mentor_id: str
    mentee_email: str
    mentor_email: str
    start_time: datetime
    end_time: datetime
    title: str
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    status: str  # pending_payment, scheduled, confirmed, completed, cancelled
    notes: Optional[str] = None
    # Payment fields
    payment_id: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = None
    payment_status: Optional[str] = None  # pending, success, failed, refunded
    razorpay_order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Bank Details Models for Razorpay Payouts
class BankAccountType(str, Enum):
    SAVINGS = "savings"
    CURRENT = "current"

class BankDetailsCreate(BaseModel):
    # UI fields
    account_name: str = Field(..., description="Account holder name")
    account_email: Optional[str] = Field(None, description="Account email")
    business_name: str = Field(..., description="Business name (usually bank name)")
    business_type: str = Field(default="individual", description="Business type (individual, partnership, company)")
    branch_ifsc_code: str = Field(
        ..., 
        max_length=11,
        description="IFSC code of the bank"
    )
    account_number: str = Field(..., description="Bank account number")
    beneficiary_name: str = Field(..., description="Name of the account holder/beneficiary")
    pan_number: str = Field(..., max_length=10, description="PAN number (10 characters)")
    phone_number: str = Field(..., description="Phone number")

class BankDetailsUpdate(BaseModel):
    account_name: Optional[str] = None
    account_email: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    branch_ifsc_code: Optional[str] = Field(None, max_length=11)
    account_number: Optional[str] = None
    beneficiary_name: Optional[str] = None
    pan_number: Optional[str] = Field(None, max_length=10)
    phone_number: Optional[str] = None

class BankDetailsResponse(BaseModel):
    id: str
    user_id: str
    account_name: str
    account_email: Optional[str] = None
    business_name: str
    business_type: str
    branch_ifsc_code: str
    account_number: str
    beneficiary_name: str
    pan_number: str
    phone_number: str
    razorpay_account_id: Optional[str] = None
    razorpay_route_account_id: Optional[str] = None

    class Config:
        from_attributes = True

# Mentor Payout System Models
class SimpleMentorSetupRequest(BaseModel):
    account_name: str = Field(..., description="Account holder name")
    account_email: str = Field(..., description="Account email")
    branch_ifsc_code: str = Field(..., description="Branch IFSC code")
    account_number: str = Field(..., description="Account number")
    beneficiary_name: str = Field(..., description="Beneficiary name")
    business_name: str = Field(..., description="Business name")
    business_type: str = Field(default="individual", description="Business type (individual, partnership, company)")

class MentorSetupRequest(BaseModel):
    business_name: str = Field(..., description="Business name for Razorpay account")
    business_type: str = Field(default="individual", description="Business type (individual, partnership, company)")
    business_registration_number: Optional[str] = Field(None, description="Business registration number")
    business_pan: Optional[str] = Field(None, description="Business PAN number")
    business_gst: Optional[str] = Field(None, description="Business GST number")
    contact_name: str = Field(..., description="Contact person name")
    contact_email: str = Field(..., description="Contact email")
    contact_mobile: str = Field(..., description="Contact mobile number")
    address: Dict[str, Any] = Field(..., description="Business address")

class MentorSetupResponse(BaseModel):
    id: str
    user_id: str
    razorpay_account_id: Optional[str] = None
    is_payout_ready: bool = False
    kyc_status: str = "pending"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SessionCreateRequest(BaseModel):
    mentor_id: str = Field(..., description="Mentor user ID")
    title: str = Field(..., description="Session title")
    description: Optional[str] = Field(None, description="Session description")
    scheduled_at: datetime = Field(..., description="When the session is scheduled")
    duration_minutes: int = Field(default=60, description="Session duration in minutes")
    amount: float = Field(..., gt=0, description="Session amount")

class SessionWithPaymentResponse(BaseModel):
    id: str
    mentee_id: str
    mentor_id: str
    title: str
    description: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    amount: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Include user details for better API responses
    mentee_name: Optional[str] = None
    mentee_email: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_email: Optional[str] = None
    
    # Payment information
    payment_id: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = None
    payment_status: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    
    # Scheduled calls information
    scheduled_call_id: Optional[str] = None
    scheduled_call_status: Optional[str] = None
    scheduled_call_title: Optional[str] = None
    scheduled_call_description: Optional[str] = None

    class Config:
        from_attributes = True

class SessionPaymentRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to pay for")

class SessionPaymentResponse(BaseModel):
    session_id: str
    razorpay_order_id: str
    amount: float
    currency: str
    key_id: str

class TransferRequest(BaseModel):
    payment_id: str = Field(..., description="Session payment ID to transfer")

class TransferResponse(BaseModel):
    id: str
    session_payment_id: str
    mentor_id: str
    razorpay_transfer_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    scheduled_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# User Time Slots Models
class TimeSlotStatus(str, Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class UserTimeSlotCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")
    timezone: str = Field(default="UTC", description="Timezone for the slot")
    title: Optional[str] = Field(None, description="Optional title for the slot")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    is_recurring: bool = Field(default=True, description="Whether this is a recurring slot")
    recurring_pattern: Optional[str] = Field(default="weekly", description="Recurring pattern (daily, weekly, monthly)")

class UserTimeSlotUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: Optional[str] = Field(None, description="Start time in HH:MM format (24-hour)")
    end_time: Optional[str] = Field(None, description="End time in HH:MM format (24-hour)")
    timezone: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[TimeSlotStatus] = None
    is_recurring: Optional[bool] = None
    recurring_pattern: Optional[str] = None

class UserTimeSlotResponse(BaseModel):
    id: str
    user_id: str
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")
    timezone: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: TimeSlotStatus
    is_recurring: bool
    recurring_pattern: Optional[str] = None
    duration_minutes: int
    created_at: datetime
    updated_at: datetime
    
    # Include user details for better API responses
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    
    # Human-readable day name
    day_name: Optional[str] = None

    class Config:
        from_attributes = True

class UserTimeSlotBulkCreate(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")
    timezone: str = Field(default="UTC", description="Timezone for the slots")
    days_of_week: List[int] = Field(..., description="Days of week (0=Monday, 6=Sunday)")
    title: Optional[str] = Field(None, description="Optional title for the slots")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    slot_duration_minutes: int = Field(default=45, description="Duration of each slot in minutes")

class UserTimeSlotDayCreate(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    timezone: str = Field(default="UTC", description="Timezone for the slots")
    title: Optional[str] = Field(None, description="Optional title for the slots")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    slot_duration_minutes: int = Field(default=45, description="Duration of each slot in minutes")
    time_slots: List[Dict[str, str]] = Field(..., description="List of time slots with start_time and end_time in HH:MM format")
    break_between_slots_minutes: int = Field(default=15, description="Break time between slots in minutes")

class DaySlotConfig(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")

class UserTimeSlotFlexibleCreate(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    timezone: str = Field(default="UTC", description="Timezone for the slots")
    title: Optional[str] = Field(None, description="Optional title for the slots")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    day_configs: List[DaySlotConfig] = Field(..., description="Configuration for each day of the week")

class UserTimeSlotWeeklyCreate(BaseModel):
    timezone: str = Field(default="UTC", description="Timezone for the slots")
    title: Optional[str] = Field(None, description="Optional title for the slots")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    day_configs: List[DaySlotConfig] = Field(..., description="Configuration for each day of the week")
    weeks_ahead: int = Field(default=4, ge=1, le=12, description="Number of weeks to create slots for")

class UserTimeSlotBulkResponse(BaseModel):
    success: bool
    message: str
    slots_created: int
    slots: List[UserTimeSlotResponse]
    date_range: Dict[str, str]
    timezone: str

class UserTimeSlotSummary(BaseModel):
    total_slots: int
    available_slots: int
    booked_slots: int
    blocked_slots: int
    upcoming_slots: int
    next_available_slot: Optional[UserTimeSlotResponse] = None
    recent_slots: List[UserTimeSlotResponse] = []
