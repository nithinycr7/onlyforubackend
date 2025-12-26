from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.db.models import FanClub, CreatorProfile, SubscriptionTier, TierType
from app.schemas import FanClubCreate, FanClubResponse, SubscriptionTierResponse
from app.core.dependencies import get_current_creator, get_current_user
from app.api.v1.creators import generate_slug

router = APIRouter()


@router.post("/create", response_model=FanClubResponse, status_code=status.HTTP_201_CREATED)
async def create_fan_club(
    club_data: FanClubCreate,
    current_user = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Create fan club for creator.
    
    - Auto-creates 3 default tiers (Text, Voice, Video)
    - Generates unique slug
    """
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found"
        )
    
    # Check if club already exists
    result = await db.execute(
        select(FanClub).where(FanClub.creator_id == creator.id)
    )
    existing_club = result.scalar_one_or_none()
    
    if existing_club:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fan club already exists"
        )
    
    # Generate unique slug
    base_slug = generate_slug(club_data.club_name)
    slug = base_slug
    counter = 1
    
    while True:
        result = await db.execute(
            select(FanClub).where(FanClub.slug == slug)
        )
        if not result.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Create fan club
    fan_club = FanClub(
        creator_id=creator.id,
        club_name=club_data.club_name,
        slug=slug,
        description=club_data.description,
        cover_image_url=club_data.cover_image_url,
    )
    
    db.add(fan_club)
    await db.flush()
    
    # Create default tiers
    default_tiers = [
        SubscriptionTier(
            club_id=fan_club.id,
            tier_name="Text Tier",
            tier_type=TierType.TEXT,
            price_inr=49.00,
            features=["10 text messages/month", "Reply within 48 hours", "Exclusive text drops"],
            max_messages_per_month=10,
            reply_sla_hours=48,
        ),
        SubscriptionTier(
            club_id=fan_club.id,
            tier_name="Voice Tier",
            tier_type=TierType.VOICE,
            price_inr=99.00,
            features=["5 voice messages/month", "Voice replies", "Reply within 48 hours", "All text tier benefits"],
            max_messages_per_month=5,
            reply_sla_hours=48,
        ),
        SubscriptionTier(
            club_id=fan_club.id,
            tier_name="Video Tier",
            tier_type=TierType.VIDEO,
            price_inr=199.00,
            features=["3 video messages/month", "Video replies", "Priority replies (24 hours)", "All previous tier benefits"],
            max_messages_per_month=3,
            reply_sla_hours=24,
        ),
    ]
    
    for tier in default_tiers:
        db.add(tier)
    
    await db.commit()
    await db.refresh(fan_club)
    
    return fan_club


@router.get("/discover", response_model=List[dict])
async def discover_clubs(
    niche: str = None,
    language: str = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Discovery feed for fan clubs.
    
    - Filter by niche, language
    - Paginated results
    - Cached for 5 minutes in production
    """
    query = (
        select(FanClub, CreatorProfile)
        .join(CreatorProfile, FanClub.creator_id == CreatorProfile.id)
        .where(FanClub.is_active == True)
        .where(CreatorProfile.verified_badge == True)
    )
    
    if niche:
        query = query.where(CreatorProfile.niche == niche)
    
    if language:
        query = query.where(CreatorProfile.language == language)
    
    query = query.order_by(CreatorProfile.active_subscribers.desc())
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    clubs_with_creators = result.all()
    
    # Format response
    response = []
    for club, creator in clubs_with_creators:
        response.append({
            "club_id": str(club.id),
            "club_name": club.club_name,
            "slug": club.slug,
            "description": club.description,
            "cover_image_url": club.cover_image_url,
            "total_members": club.total_members,
            "creator": {
                "display_name": creator.display_name,
                "slug": creator.slug,
                "niche": creator.niche,
                "language": creator.language,
                "verified_badge": creator.verified_badge,
                "avg_response_time_hours": creator.avg_response_time_hours,
            }
        })
    
    return response


@router.get("/{slug}", response_model=dict)
async def get_club_details(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get fan club details with tiers.
    
    - Public club information
    - Available subscription tiers
    """
    result = await db.execute(
        select(FanClub, CreatorProfile)
        .join(CreatorProfile, FanClub.creator_id == CreatorProfile.id)
        .where(FanClub.slug == slug)
    )
    club_with_creator = result.first()
    
    if not club_with_creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found"
        )
    
    club, creator = club_with_creator
    
    # Get tiers
    result = await db.execute(
        select(SubscriptionTier)
        .where(SubscriptionTier.club_id == club.id)
        .where(SubscriptionTier.is_active == True)
        .order_by(SubscriptionTier.price_inr)
    )
    tiers = result.scalars().all()
    
    return {
        "club": {
            "id": str(club.id),
            "club_name": club.club_name,
            "slug": club.slug,
            "description": club.description,
            "cover_image_url": club.cover_image_url,
            "total_members": club.total_members,
        },
        "creator": {
            "id": str(creator.id),
            "display_name": creator.display_name,
            "slug": creator.slug,
            "bio": creator.bio,
            "niche": creator.niche,
            "language": creator.language,
            "social_links": creator.social_links,
            "verified_badge": creator.verified_badge,
            "avg_response_time_hours": creator.avg_response_time_hours,
            "active_subscribers": creator.active_subscribers,
        },
        "tiers": [
            {
                "id": str(tier.id),
                "tier_name": tier.tier_name,
                "tier_type": tier.tier_type,
                "price_inr": float(tier.price_inr),
                "features": tier.features,
                "max_messages_per_month": tier.max_messages_per_month,
                "reply_sla_hours": tier.reply_sla_hours,
            }
            for tier in tiers
        ]
    }
