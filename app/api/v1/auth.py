from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.db.models import User
from app.schemas import (
    UserRegister,
    UserLogin,
    Token,
    TokenRefresh,
    PhoneVerification,
    OTPConfirmation,
    UserResponse,
    PhoneLoginRequest,
    UserProfileUpdate,
)
import uuid
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_referral_code,
)
from app.api.deps import get_current_user

router = APIRouter()

# Mock OTP storage (use Redis in production)
otp_storage = {}


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user (creator or fan).
    
    - Creates user account with hashed password
    - Generates unique referral code
    - Tracks referral if referral_code provided
    - Returns JWT access and refresh tokens
    """
    print(f"DEBUG: Register attempt for {user_data.email}")
    # Check if email already exists
    print("DEBUG: Checking email existence...")
    result = await db.execute(select(User).where(User.email == user_data.email))
    print("DEBUG: Email check done.")
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone already exists (if provided)
    if user_data.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        existing_phone = result.scalar_one_or_none()
        
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
    
    print("DEBUG: Creating new user object...")
    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        phone=user_data.phone,
        role=user_data.role,
    )
    
    print("DEBUG: Adding user to session...")
    db.add(new_user)
    print("DEBUG: Flushing session...")
    await db.flush()  # Get user ID
    print("DEBUG: Flush successful.")
    
    # Generate referral code
    new_user.referral_code = generate_referral_code(str(new_user.id))
    
    # Track referral if provided
    if user_data.referral_code:
        result = await db.execute(
            select(User).where(User.referral_code == user_data.referral_code)
        )
        referrer = result.scalar_one_or_none()
        
        if referrer:
            new_user.referred_by = referrer.id
    
    print("DEBUG: Committing transaction...")
    await db.commit()
    print("DEBUG: Commit successful.")
    await db.refresh(new_user)
    print("DEBUG: Refresh successful.")
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(new_user.id)})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        role=new_user.role.value if hasattr(new_user.role, 'value') else new_user.role,
    )


@router.post("/access-token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login.
    
    - Validates credentials
    - Returns JWT access and refresh tokens
    """
    # Get user by email (OAuth2 uses 'username' field for email)
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role.value if hasattr(user.role, 'value') else user.role
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    - Validates refresh token
    - Returns new access token
    """
    payload = decode_token(token_data.refresh_token, token_type="refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user_id = payload.get("sub")
    
    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/verify-phone", status_code=status.HTTP_200_OK)
async def verify_phone(phone_data: PhoneVerification):
    """
    Send OTP to phone number for verification.
    
    - Generates 6-digit OTP
    - Sends via SMS (mocked in development)
    - OTP valid for 10 minutes
    """
    import random
    
    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP (use Redis with TTL in production)
    otp_storage[phone_data.phone] = otp
    
    # Mock SMS sending in development
    print(f"📱 OTP for {phone_data.phone}: {otp}")
    
    # In production, send via Twilio/MSG91:
    # await send_sms(phone_data.phone, f"Your OnlyForU OTP is: {otp}")
    
    return {
        "message": "OTP sent successfully",
        "phone": phone_data.phone,
        # Include OTP in response for development only
        "otp": otp if settings.is_development else None,
    }


@router.post("/confirm-otp", response_model=UserResponse)
async def confirm_otp(
    otp_data: OTPConfirmation,
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm OTP and mark phone as verified.
    
    - Validates OTP
    - Updates user's phone verification status
    """
    # Check OTP
    stored_otp = otp_storage.get(otp_data.phone)
    
    if not stored_otp or stored_otp != otp_data.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )
    
    # Get user by phone
    result = await db.execute(select(User).where(User.phone == otp_data.phone))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Mark as verified
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    
    # Clear OTP
    del otp_storage[otp_data.phone]
    
    return user


@router.post("/phone/verify", response_model=Token)
async def verify_phone_login(
    login_data: PhoneLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify Firebase phone authentication and return JWT token.
    
    Flow:
    1. Verify Firebase token
    2. Get/create user with phone number
    3. Return JWT tokens
    """
    from app.core.firebase import verify_firebase_token, initialize_firebase
    
    # Initialize Firebase if not already done
    initialize_firebase()
    
    try:
        # Verify Firebase token
        firebase_user = verify_firebase_token(login_data.firebase_token)
        
        # Use phone from login_data for safety, as Firebase phone_number might be None in some configs
        phone = login_data.phone
        
        # Check if user exists
        result = await db.execute(
            select(User).filter(User.phone == phone)
        )
        user = result.scalar_one_or_none()
        is_new_user = False
        
        # Create user if doesn't exist
        if not user:
            is_new_user = True
            # Use role from request for new users (creator or fan)
            user_role = login_data.role if hasattr(login_data, 'role') and login_data.role else 'fan'
            user = User(
                phone=phone,
                email=f"user_{phone[-4:]}_{uuid.uuid4().hex[:4]}@placeholder.com", # Placeholder email
                full_name=f"User {phone[-4:]}",  # Default name
                role=user_role,  # Use selected role from frontend
                password_hash=get_password_hash(uuid.uuid4().hex), # Strong random password
                is_verified=True,  # Phone verified via Firebase
                is_active=True
            )
            db.add(user)
            await db.flush() # Get user.id
            
            # Generate referral code
            user.referral_code = generate_referral_code(str(user.id))
            
            await db.commit()
            await db.refresh(user)
        
        # Generate JWT tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        # Handle role enum vs string
        role_val = user.role.value if hasattr(user.role, 'value') else user.role
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            role=role_val,
            is_new_user=is_new_user
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        await db.rollback()
        print(f"Error in phone login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during verification"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user's basic profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile (name and email).
    Used during phone onboarding.
    """
    # Check if email is already taken by another user
    if user_update.email != current_user.email:
        result = await db.execute(
            select(User).where(User.email == user_update.email).where(User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = user_update.email
    
    current_user.full_name = user_update.full_name
    
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout():
    """
    Logout user (invalidate refresh token).
    
    - In production, add refresh token to Redis blacklist
    - Client should delete tokens from storage
    """
    # In production: Add refresh token to Redis blacklist
    # await redis.setex(f"blacklist:{refresh_token}", settings.refresh_token_expire_days * 86400, "1")
    
    return {"message": "Logged out successfully"}
