from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.db.session import get_db
from app.db.models import ContentDrop, CreatorProfile, User, FanClub, VerificationStatus
from app.schemas import ContentDropResponse, CreatorProfileResponse
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=List[ContentDropResponse])
async def get_main_feed(
    skip: int = 0,
    limit: int = 20,
    niche: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated feed of content drops.
    
    - Returns latest drops from all creators
    - Supports filtering by niche (e.g. 'cooking', 'tech')
    """
    query = (
        select(ContentDrop, CreatorProfile)
        .join(CreatorProfile, ContentDrop.creator_id == CreatorProfile.id)
        .order_by(desc(ContentDrop.created_at))
        .offset(skip)
        .limit(limit)
    )

@router.get("/drops", response_model=List[ContentDropResponse])
async def get_recent_drops(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get most recent content drops from subscribed creators.
    """
    from app.db.models import Subscription
    
    # Get subscribed creator IDs
    subs_result = await db.execute(
        select(Subscription.creator_id).where(Subscription.fan_id == current_user.id)
    )
    subscribed_creator_ids = [row[0] for row in subs_result.all()]
    
    if not subscribed_creator_ids:
        return []
    
    # Fetch recent drops
    query = (
        select(ContentDrop)
        .where(ContentDrop.creator_id.in_(subscribed_creator_ids))
        .order_by(ContentDrop.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    drops = result.scalars().all()
    
    return drops


@router.get("/trending", response_model=List[CreatorProfileResponse])
async def get_trending_creators(
    limit: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """
    Get trending creators based on active subscribers/follower count.
    """
    # Fetch trending creator profiles with packages eagerly loaded
    result = await db.execute(
        select(CreatorProfile)
        .options(selectinload(CreatorProfile.packages))
        .where(CreatorProfile.verification_status == VerificationStatus.APPROVED)
        .order_by(CreatorProfile.follower_count.desc())
        .limit(limit)
    )
    
    creators = result.scalars().all()
    return creators
