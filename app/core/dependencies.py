from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User
from app.core.security import decode_token

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token
    token = credentials.credentials
    payload = decode_token(token, token_type="access")
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_creator(current_user: User = Depends(get_current_user)) -> User:
    """Verify current user is a creator."""
    if current_user.role != "creator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creators can access this resource"
        )
    return current_user


async def get_current_fan(current_user: User = Depends(get_current_user)) -> User:
    """Verify current user is a fan."""
    if current_user.role != "fan":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only fans can access this resource"
        )
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verify current user is an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
