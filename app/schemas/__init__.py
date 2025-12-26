from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, date
from uuid import UUID


# ============= Auth Schemas =============

class UserRegister(BaseModel):
    """User registration schema."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)  # bcrypt limit is 72 bytes
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')
    role: str = Field(..., pattern='^(creator|fan)$')
    referral_code: Optional[str] = None


class UserLogin(BaseModel):
    """User login schema."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    is_new_user: bool = False


class TokenRefresh(BaseModel):
    """Refresh token request."""
    refresh_token: str


class PhoneVerification(BaseModel):
    """Phone verification request."""
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')


class OTPConfirmation(BaseModel):
    """OTP confirmation request."""
    phone: str
    otp: str = Field(..., pattern=r'^\d{6}$')


class PhoneLoginRequest(BaseModel):
    """Firebase phone login verification request."""
    firebase_token: str
    phone: str
    role: Optional[str] = Field(default='fan', pattern='^(creator|fan)$')


# ============= User Schemas =============

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str
    role: str


class UserResponse(UserBase):
    """User response schema."""
    id: UUID
    phone: Optional[str]
    profile_image_url: Optional[str]
    is_verified: bool
    is_active: bool
    referral_code: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """User profile update schema (for onboarding)."""
    full_name: str = Field(..., min_length=2, max_length=255)
    email: Optional[EmailStr] = None


# ============= Service Package Schemas =============

class ServicePackageCreate(BaseModel):
    """Create consultation service package."""
    title: str = Field(..., min_length=5, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    package_type: str = Field(default="resolution", pattern='^(resolution|greeting|membership)$')
    price_inr: float = Field(..., ge=99, le=99999)
    response_modes: List[str] = Field(default=["voice"], min_items=1)
    features: List[str] = Field(default_factory=list, max_items=10)
    sla_hours: int = Field(default=48, ge=1, le=168)
    includes_followups: bool = False
    max_followups: int = Field(default=0, ge=0, le=10)
    followup_window_days: int = Field(default=7, ge=1, le=90)
    max_slots_per_month: Optional[int] = Field(None, ge=1, le=1000)
    is_popular: bool = False
    display_order: int = 0
    
    @validator('response_modes')
    def validate_response_modes(cls, v):
        valid_modes = {'voice', 'video', 'live'}
        if not all(mode in valid_modes for mode in v):
            raise ValueError(f'Invalid response mode. Must be one of: {valid_modes}')
        return v


class ServicePackageUpdate(BaseModel):
    """Update consultation service package."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    subtitle: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    price_inr: Optional[float] = Field(None, ge=99, le=99999)
    response_modes: Optional[List[str]] = None
    features: Optional[List[str]] = Field(None, max_items=10)
    sla_hours: Optional[int] = Field(None, ge=1, le=168)
    includes_followups: Optional[bool] = None
    max_followups: Optional[int] = Field(None, ge=0, le=10)
    followup_window_days: Optional[int] = Field(None, ge=1, le=90)
    max_slots_per_month: Optional[int] = Field(None, ge=1, le=1000)
    is_popular: Optional[bool] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class ServicePackageResponse(BaseModel):
    """Service package response."""
    id: UUID
    creator_id: UUID
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    package_type: str
    price_inr: float
    response_modes: List[str]
    features: List[str]
    sla_hours: int
    includes_followups: bool
    max_followups: int
    followup_window_days: int
    max_slots_per_month: Optional[int]
    is_active: bool
    is_popular: bool
    display_order: int
    # System-populated fields
    current_slots_used: int
    avg_rating: float
    total_purchases: int
    total_revenue: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============= Creator Schemas =============

class CreatorOnboard(BaseModel):
    """Creator onboarding schema - requires prior signup."""
    display_name: str = Field(..., min_length=2, max_length=100)
    bio: str = Field(..., min_length=5, max_length=1000)
    niche: str = Field(..., min_length=2, max_length=50)
    language: str = Field(default="telugu", pattern='^(telugu|hindi|tamil|english)$')
    social_links: Dict[str, str] = Field(default_factory=dict, description="Social media links (youtube, instagram, etc.)")
    profile_image_url: Optional[str] = None
    packages: List[ServicePackageCreate] = []
    
    
    # @validator('social_links')
    # def validate_social_links(cls, v):
    #    """Validate social links contain at least one platform."""
    #    if not v or len(v) == 0:
    #        raise ValueError('At least one social media link is required')
    #    return v


class CreatorProfileResponse(BaseModel):
    """Creator profile response."""
    id: UUID
    user_id: UUID
    display_name: str
    slug: str
    bio: str
    niche: str
    vertical: str
    language: str
    social_links: dict
    profile_image_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    follower_count: int
    verification_status: str
    verified_badge: bool
    avg_response_time_hours: Optional[int]
    total_earnings: float
    active_subscribers: int
    created_at: datetime
    packages: List[ServicePackageResponse] = []
    
    class Config:
        from_attributes = True


# ============= Message Schemas =============

class MessageCreate(BaseModel):
    """Create message request."""
    subscription_id: UUID
    message_type: str = Field(..., pattern='^(text|voice|video)$')
    content: Optional[str] = Field(None, max_length=500)
    media_url: Optional[str] = None
    media_duration_secs: Optional[int] = None


class MessageResponse(BaseModel):
    """Message response."""
    id: UUID
    subscription_id: UUID
    sender_id: UUID
    receiver_id: UUID
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    media_duration_secs: Optional[int]
    status: str
    is_fan_message: bool
    replied_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ThreadResponse(BaseModel):
    subscription_id: str
    title: str
    subtitle: str
    status: str
    messages: List[MessageResponse]
    current_user_id: str  # To help frontend identify 'own' messages





class CreatorDashboard(BaseModel):
    """Creator dashboard statistics."""
    total_earnings: float
    active_subscribers: int
    pending_messages: int
    avg_response_time: Optional[str]
    revenue_chart: List[dict]
    subscriber_growth: List[dict]
    tier_breakdown: List[dict]


# ============= Fan Club Schemas =============

class FanClubCreate(BaseModel):
    """Fan club creation schema."""
    club_name: str = Field(..., min_length=5, max_length=150)
    description: str = Field(..., min_length=50, max_length=1000)
    cover_image_url: Optional[str] = None


class FanClubResponse(BaseModel):
    """Fan club response."""
    id: UUID
    creator_id: UUID
    club_name: str
    slug: str
    description: str
    cover_image_url: Optional[str]
    is_active: bool
    total_members: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= Subscription Tier Schemas =============

class SubscriptionTierCreate(BaseModel):
    """Subscription tier creation."""
    tier_name: str
    tier_type: str = Field(..., pattern='^(text|voice|video)$')
    price_inr: float = Field(..., gt=0, le=10000)
    features: List[str]
    max_messages_per_month: int = Field(..., gt=0, le=100)
    reply_sla_hours: int = Field(default=48, ge=24, le=168)


class SubscriptionTierResponse(BaseModel):
    """Subscription tier response."""
    id: UUID
    club_id: UUID
    tier_name: str
    tier_type: str
    price_inr: float
    features: List[str]
    max_messages_per_month: int
    reply_sla_hours: int
    is_active: bool
    
    class Config:
        from_attributes = True


# ============= Subscription Schemas =============

class SubscriptionCreate(BaseModel):
    """Create subscription request."""
    tier_id: UUID
    payment_method: str = "razorpay"


class SubscriptionResponse(BaseModel):
    """Subscription response."""
    id: UUID
    fan_id: UUID
    tier_id: UUID
    club_id: UUID
    creator_id: UUID
    status: str
    current_period_start: date
    current_period_end: date
    next_billing_date: Optional[date]
    messages_sent_this_period: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaymentConfirmation(BaseModel):
    """Payment confirmation from Razorpay."""
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    subscription_id: UUID




# ============= Content Drop Schemas =============

class ContentDropCreate(BaseModel):
    """Create content drop."""
    title: str = Field(..., min_length=5, max_length=200)
    caption: Optional[str] = Field(None, max_length=1000)
    media_url: str
    media_type: str = Field(..., pattern='^(voice|video|image)$')
    is_pinned: bool = False


class ContentDropResponse(BaseModel):
    """Content drop response."""
    id: UUID
    creator_id: UUID
    club_id: UUID
    title: str
    caption: Optional[str]
    media_url: str
    media_type: str
    is_pinned: bool
    view_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= Media Schemas =============

class MediaUploadRequest(BaseModel):
    """Media upload URL request."""
    file_name: str
    file_size: int = Field(..., gt=0, le=104857600)  # Max 100MB
    media_type: str = Field(..., pattern='^(image|voice|video)$')


class MediaUploadResponse(BaseModel):
    """Media upload URL response."""
    upload_url: str
    blob_url: str
    expires_in: int = 3600  # 1 hour


# ============= Booking Schemas =============

class BookingCreate(BaseModel):
    """Create a new booking."""
    service_id: Optional[UUID] = None
    creator_id: UUID
    service_title: str
    service_subtitle: Optional[str] = None
    amount_paid: float


class BookingResponse(BaseModel):
    """Booking response."""
    id: UUID
    fan_id: UUID
    creator_id: UUID
    service_id: Optional[UUID] = None
    service_title: Optional[str] = None
    service_subtitle: Optional[str] = None
    status: str
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    question_audio_url: Optional[str] = None
    question_video_url: Optional[str] = None
    question_submitted_at: Optional[datetime] = None
    response_media_url: Optional[str] = None
    response_type: Optional[str] = None
    response_submitted_at: Optional[datetime] = None
    expected_response_by: Optional[datetime] = None
    sla_met: Optional[bool] = None
    fan_rating: Optional[int] = None
    fan_review: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookingWithDetails(BookingResponse):
    """Booking with service and creator details."""
    service_title: str
    service_subtitle: Optional[str] = None
    creator_display_name: str
    creator_slug: str
    amount_paid: float


class RatingSubmit(BaseModel):
    """Submit rating for a booking."""
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)


class CreatorBookingResponse(BaseModel):
    """Booking response for creator dashboard with fan details."""
    id: UUID
    fan_id: UUID
    fan_name: str
    fan_email: str
    fan_profile_image_url: Optional[str] = None
    service_title: Optional[str] = None
    service_subtitle: Optional[str] = None
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    question_audio_url: Optional[str] = None
    question_video_url: Optional[str] = None
    question_submitted_at: Optional[datetime] = None
    response_media_url: Optional[str] = None
    response_type: Optional[str] = None
    response_submitted_at: Optional[datetime] = None
    status: str
    expected_response_by: Optional[datetime] = None
    sla_met: Optional[bool] = None
    amount_paid: float
    created_at: datetime
    updated_at: datetime


# ============= Follow-up Message Schemas =============

class FollowUpMessageCreate(BaseModel):
    """Create a follow-up message."""
    message_type: str = Field(..., pattern='^(text|audio|video)$')
    text_content: Optional[str] = None


class FollowUpMessageResponse(BaseModel):
    """Follow-up message response."""
    id: UUID
    booking_id: UUID
    sender_type: str  # 'fan' or 'creator'
    message_type: str  # 'text', 'audio', 'video'
    text_content: Optional[str] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= Payment Schemas =============

class PaymentOrderCreate(BaseModel):
    """Schema for creating a payment order."""
    booking_id: UUID


class PaymentVerify(BaseModel):
    """Schema for verifying a payment."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentOrderResponse(BaseModel):
    """Schema for payment order response."""
    order_id: str
    currency: str
    amount: int  # in paise
    key_id: str
    booking_id: UUID
