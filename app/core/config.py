from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    environment: str = "development"
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # JWT
    jwt_secret_key: str
    jwt_refresh_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # Storage
    storage_provider: str = "minio"  # minio or azure
    
    # MinIO (local development)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_secure: bool = False
    minio_bucket_profile_images: str = "profile-images"
    minio_bucket_voice_notes: str = "voice-notes"
    minio_bucket_video_replies: str = "video-replies"
    minio_bucket_drops: str = "drops"
    
    # Azure Storage (production)
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    
    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    
    # SendGrid
    sendgrid_api_key: str = ""
    from_email: str = "noreply@onlyforu.app"
    
    # SMS
    sms_provider: str = "mock"  # mock, twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    
    # Content Moderation
    content_moderation_enabled: bool = False
    azure_content_moderator_endpoint: str = ""
    azure_content_moderator_key: str = ""
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    
    # Platform Settings
    platform_fee_percentage: int = 15
    referral_reward_inr: float = 50.0
    default_reply_sla_hours: int = 48
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"


# Global settings instance
settings = Settings()
