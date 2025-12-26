"""
API Dependencies
Authentication and authorization dependencies for FastAPI endpoints
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from typing import Optional

from app.db.session import get_db
from app.db.models import User
from app.core.config import settings

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    """
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_creator(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that the current user is a creator.
    """
    if current_user.role != "creator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creator access required"
        )
    return current_user


async def get_current_fan(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify that the current user is a fan.
    """
    if current_user.role != "fan":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fan access required"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise None.
    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalar_one_or_none()
        
        return user if user and user.is_active else None
    except JWTError:
        return None
