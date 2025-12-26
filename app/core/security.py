from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# Password hashing context - explicitly handle bcrypt's 72-byte limit
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__default_rounds=12,
    bcrypt__truncate_error=False  # Auto-truncate passwords longer than 72 bytes
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    print("DEBUG: Hashing password...")
    hashed = pwd_context.hash(password)
    print("DEBUG: Password hashed.")
    return hashed


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_refresh_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str, token_type: str = "access") -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        secret_key = settings.jwt_secret_key if token_type == "access" else settings.jwt_refresh_secret_key
        payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
        
        # Verify token type
        if payload.get("type") != token_type:
            return None
        
        return payload
    except JWTError:
        return None


def generate_referral_code(user_id: str) -> str:
    """Generate unique referral code from user ID."""
    import hashlib
    import base64
    
    # Create hash of user ID
    hash_object = hashlib.sha256(user_id.encode())
    hash_digest = hash_object.digest()
    
    # Convert to base64 and take first 8 characters
    code = base64.urlsafe_b64encode(hash_digest).decode()[:8].upper()
    return code
