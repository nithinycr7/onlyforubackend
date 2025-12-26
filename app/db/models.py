from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, Text, ForeignKey, Enum, CheckConstraint, Index, DECIMAL, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from app.db.session import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    CREATOR = "creator"
    FAN = "fan"
    ADMIN = "admin"


class VerificationStatus(str, enum.Enum):
    """Creator verification status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class MessageStatus(str, enum.Enum):
    """Message status."""
    PENDING = "pending"
    REPLIED = "replied"
    ARCHIVED = "archived"


class TransactionStatus(str, enum.Enum):
    """Transaction status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class TierType(str, enum.Enum):
    """Subscription tier type."""
    TEXT = "text"
    VOICE = "voice"
    VIDEO = "video"


class CreatorVertical(str, enum.Enum):
    """Creator vertical type."""
    RESOLVE = "resolve"  # Professional services, queries with SLA
    CONNECT = "connect"  # Community engagement, fan clubs


class PackageType(str, enum.Enum):
    """Service package type."""
    RESOLUTION = "resolution"  # Resolve vertical: problem-solving services
    GREETING = "greeting"      # Connect vertical: personal messages
    MEMBERSHIP = "membership"  # Connect vertical: community access


class BookingStatus(str, enum.Enum):
    """Booking/consultation status."""
    PENDING_QUESTION = "pending_question"  # Booking created, waiting for fan to submit question
    AWAITING_RESPONSE = "awaiting_response"  # Question submitted, waiting for creator response
    COMPLETED = "completed"  # Creator responded, consultation complete
    CANCELLED = "cancelled"  # Booking cancelled


class ResponseType(str, enum.Enum):
    """Creator response type."""
    VOICE = "voice"
    VIDEO = "video"


class User(Base):
    """User model for both creators and fans."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(15), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String(255), nullable=False)
    profile_image_url = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    referral_code = Column(String(20), unique=True, nullable=True, index=True)
    referred_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator_profile = relationship("CreatorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", foreign_keys="Subscription.fan_id", back_populates="fan")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    
    __table_args__ = (
        Index("idx_users_role_active", "role", "is_active"),
    )


class CreatorProfile(Base):
    """Creator-specific profile information."""
    __tablename__ = "creator_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    bio = Column(Text, nullable=False)
    niche = Column(String(50), nullable=False)
    vertical = Column(Enum(CreatorVertical), default=CreatorVertical.CONNECT, nullable=False)
    language = Column(String(50), default="telugu")
    social_links = Column(JSONB, nullable=False)  # {"youtube": "url", "instagram": "url"}
    follower_count = Column(Integer, default=0)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    verified_badge = Column(Boolean, default=False)
    avg_response_time_hours = Column(Integer, nullable=True)
    total_earnings = Column(DECIMAL(10, 2), default=0)
    active_subscribers = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="creator_profile")
    fan_club = relationship("FanClub", back_populates="creator", uselist=False, cascade="all, delete-orphan")
    content_drops = relationship("ContentDrop", back_populates="creator", cascade="all, delete-orphan")
    packages = relationship("ServicePackage", back_populates="creator", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_creator_verification", "verification_status"),
        Index("idx_creator_niche_lang", "niche", "language"),
        Index("idx_creator_active_subs", "active_subscribers"),
    )


class ServicePackage(Base):
    """Service packages (consultation services) that creators sell."""
    __tablename__ = "service_packages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # CREATOR-EDITABLE FIELDS
    title = Column(String(200), nullable=False)
    subtitle = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    package_type = Column(Enum(PackageType), default=PackageType.RESOLUTION)
    price_inr = Column(DECIMAL(10, 2), nullable=False)
    response_modes = Column(JSONB, nullable=False, server_default='["voice"]')  # ["voice", "video"]
    features = Column(JSONB, nullable=False, server_default='[]')  # List of feature strings
    sla_hours = Column(Integer, default=48, nullable=False)
    includes_followups = Column(Boolean, default=False)
    max_followups = Column(Integer, default=0)
    followup_window_days = Column(Integer, default=7)
    max_slots_per_month = Column(Integer, nullable=True)  # NULL = unlimited
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    # SYSTEM-POPULATED FIELDS
    current_slots_used = Column(Integer, default=0)
    avg_rating = Column(DECIMAL(3, 2), default=0.0)
    total_purchases = Column(Integer, default=0)
    total_revenue = Column(DECIMAL(12, 2), default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("CreatorProfile", back_populates="packages")
    
    __table_args__ = (
        Index("idx_packages_creator", "creator_id", "is_active"),
        Index("idx_packages_price", "price_inr"),
        CheckConstraint("price_inr >= 99 AND price_inr <= 99999", name="valid_price"),
        CheckConstraint("max_followups >= 0 AND max_followups <= 10", name="valid_followups"),
        CheckConstraint("sla_hours > 0 AND sla_hours <= 168", name="valid_sla"),
    )


class FanClub(Base):
    """Fan club for each creator."""
    __tablename__ = "fan_clubs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("creator_profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    club_name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    cover_image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    total_members = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    creator = relationship("CreatorProfile", back_populates="fan_club")
    subscription_tiers = relationship("SubscriptionTier", back_populates="club", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="club")
    content_drops = relationship("ContentDrop", back_populates="club")


class SubscriptionTier(Base):
    """Subscription pricing tiers."""
    __tablename__ = "subscription_tiers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id = Column(UUID(as_uuid=True), ForeignKey("fan_clubs.id", ondelete="CASCADE"), nullable=False)
    tier_name = Column(String(100), nullable=False)
    tier_type = Column(Enum(TierType), nullable=False)
    price_inr = Column(DECIMAL(10, 2), nullable=False)
    features = Column(JSONB, nullable=False)  # ["Reply within 48hrs", "Exclusive drops"]
    max_messages_per_month = Column(Integer, nullable=True)
    reply_sla_hours = Column(Integer, default=48)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    club = relationship("FanClub", back_populates="subscription_tiers")
    subscriptions = relationship("Subscription", back_populates="tier")
    
    __table_args__ = (
        Index("idx_tiers_club", "club_id"),
        Index("idx_tiers_club_type", "club_id", "tier_type", unique=True),
    )


class Subscription(Base):
    """Active fan subscriptions."""
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tier_id = Column(UUID(as_uuid=True), ForeignKey("subscription_tiers.id"), nullable=False)
    club_id = Column(UUID(as_uuid=True), ForeignKey("fan_clubs.id"), nullable=False)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("creator_profiles.id"), nullable=False)
    razorpay_subscription_id = Column(String(100), unique=True, nullable=True)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    current_period_start = Column(Date, nullable=False)
    current_period_end = Column(Date, nullable=False)
    next_billing_date = Column(Date, nullable=True)
    messages_sent_this_period = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    fan = relationship("User", foreign_keys=[fan_id], back_populates="subscriptions")
    tier = relationship("SubscriptionTier", back_populates="subscriptions")
    club = relationship("FanClub", back_populates="subscriptions")
    messages = relationship("Message", back_populates="subscription", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="subscription")
    
    __table_args__ = (
        Index("idx_subs_fan_active", "fan_id", "status"),
        Index("idx_subs_creator_active", "creator_id", "status"),
        Index("idx_subs_next_billing", "next_billing_date"),
    )


class Message(Base):
    """Messages between fans and creators."""
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    message_type = Column(Enum(TierType), nullable=False)
    content = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    media_duration_secs = Column(Integer, nullable=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
    is_fan_message = Column(Boolean, nullable=False)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    subscription = relationship("Subscription", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    
    __table_args__ = (
        Index("idx_messages_subscription", "subscription_id", "created_at"),
        Index("idx_messages_creator_pending", "receiver_id", "status"),
        Index("idx_messages_fan_history", "sender_id", "created_at"),
    )


class ContentDrop(Base):
    """Content drops from creators to all subscribers."""
    __tablename__ = "content_drops"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False)
    club_id = Column(UUID(as_uuid=True), ForeignKey("fan_clubs.id"), nullable=False)
    title = Column(String(200), nullable=False)
    caption = Column(Text, nullable=True)
    media_url = Column(Text, nullable=False)
    media_type = Column(String(20), nullable=False)
    is_pinned = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    creator = relationship("CreatorProfile", back_populates="content_drops")
    club = relationship("FanClub", back_populates="content_drops")
    
    __table_args__ = (
        Index("idx_drops_club_created", "club_id", "created_at"),
    )


class Transaction(Base):
    """Payment transactions."""
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("service_packages.id"), nullable=True)
    razorpay_payment_id = Column(String(100), unique=True, nullable=True)
    razorpay_order_id = Column(String(100), nullable=True)
    amount_inr = Column(DECIMAL(10, 2), nullable=False)
    platform_fee_inr = Column(DECIMAL(10, 2), nullable=False)
    creator_payout_inr = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    payment_method = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    subscription = relationship("Subscription", back_populates="transactions")
    package = relationship("ServicePackage")
    
    __table_args__ = (
        Index("idx_transactions_user", "user_id", "created_at"),
        Index("idx_transactions_subscription", "subscription_id", "status"),
    )


class Referral(Base):
    """Referral tracking for viral growth."""
    __tablename__ = "referrals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    club_id = Column(UUID(as_uuid=True), ForeignKey("fan_clubs.id"), nullable=True)
    reward_status = Column(String(20), default="pending")
    reward_amount_inr = Column(DECIMAL(10, 2), default=50.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_referrals_referrer", "referrer_id"),
    )


class ContentReport(Base):
    """Content moderation reports."""
    __tablename__ = "content_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reported_item_type = Column(String(20), nullable=False)
    reported_item_id = Column(UUID(as_uuid=True), nullable=False)
    reason = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_reports_status", "status", "created_at"),
    )


class Booking(Base):
    """Consultation booking for fan-creator interactions."""
    __tablename__ = "bookings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fan_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("creator_profiles.id", ondelete="CASCADE"), nullable=False)
    # Flexible service_id for MVP (snapshot model)
    service_id = Column(UUID(as_uuid=True), nullable=True) 
    service_title = Column(String(255), nullable=True)
    service_subtitle = Column(String(255), nullable=True)
    
    # Question
    question_type = Column(String(20), nullable=True)  # 'text', 'audio', 'video'
    question_text = Column(Text, nullable=True)
    question_audio_url = Column(Text, nullable=True)
    question_video_url = Column(Text, nullable=True)
    question_submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Response
    response_media_url = Column(Text, nullable=True)
    response_type = Column(Enum(ResponseType, name="response_type_v2", native_enum=False), nullable=True)
    response_submitted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(Enum(BookingStatus, name="booking_status_v2", native_enum=False), nullable=False, server_default="pending_question")
    payment_status = Column(String(50), nullable=True)
    
    # Razorpay Details
    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(200), nullable=True)
    
    # Pricing
    amount_paid = Column(DECIMAL(10, 2), server_default="0")
    platform_fee = Column(DECIMAL(10, 2), server_default="0")
    creator_earnings = Column(DECIMAL(10, 2), server_default="0")
    
    # SLA tracking
    expected_response_by = Column(DateTime(timezone=True), nullable=True)
    sla_met = Column(Boolean, nullable=True)
    
    # Follow-ups
    follow_ups_remaining = Column(Integer, server_default="0")
    
    # Ratings
    fan_rating = Column(Integer, nullable=True)
    fan_review = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    fan = relationship("User", foreign_keys=[fan_id])
    creator = relationship("CreatorProfile", foreign_keys=[creator_id])
    # service = relationship("ServicePackage", foreign_keys=[service_id]) # Removed for Snapshot Model
    
    __table_args__ = (
        CheckConstraint("fan_rating >= 1 AND fan_rating <= 5", name="check_rating_range"),
        Index("idx_bookings_fan", "fan_id"),
        Index("idx_bookings_creator", "creator_id"),
        Index("idx_bookings_status", "status"),
        Index("idx_bookings_created", "created_at"),
    )


class FollowUpMessage(Base):
    """Follow-up messages in a consultation conversation."""
    __tablename__ = "follow_up_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    sender_type = Column(String(20), nullable=False)  # 'fan' or 'creator'
    message_type = Column(String(20), nullable=False)  # 'text', 'audio', 'video'
    
    # Content
    text_content = Column(Text, nullable=True)
    audio_url = Column(Text, nullable=True)
    video_url = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    booking = relationship("Booking", foreign_keys=[booking_id])
    
    __table_args__ = (
        Index("idx_follow_up_messages_booking", "booking_id"),
        Index("idx_follow_up_messages_created", "created_at"),
    )
