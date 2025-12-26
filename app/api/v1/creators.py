from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import re

from app.db.session import get_db
from app.db.models import User, CreatorProfile, VerificationStatus, UserRole, CreatorVertical, FanClub, SubscriptionTier, Message, MessageStatus
from app.schemas import (
    CreatorOnboard,
    CreatorProfileResponse,
    CreatorDashboard,
    MessageResponse,
    ContentDropCreate,
    ContentDropResponse,
    ServicePackageResponse,
    ServicePackageCreate,
)
from app.core.dependencies import get_current_creator

router = APIRouter()


def generate_slug(text: str) -> str:
    """Generate URL-safe slug from text."""
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces with hyphens
    slug = re.sub(r'\s+', '-', slug)
    # Remove special characters
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


@router.post("/onboard", response_model=CreatorProfileResponse, status_code=status.HTTP_201_CREATED)
async def onboard_creator(
    profile_data: CreatorOnboard,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete creator onboarding (requires prior signup + login).
    
    - Creates creator profile with auto-generated slug
    - Auto-approves creator (verification_status=APPROVED)
    - Returns complete profile with packages
    """
    # Check if creator profile already exists
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    existing_profile = result.scalar_one_or_none()
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creator profile already exists"
        )
    
    # Generate unique slug
    base_slug = generate_slug(profile_data.display_name)
    slug = base_slug
    counter = 1
    
    while True:
        result = await db.execute(
            select(CreatorProfile).where(CreatorProfile.slug == slug)
        )
        if not result.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Update user's profile image if provided
    if profile_data.profile_image_url:
        current_user.profile_image_url = profile_data.profile_image_url
    
    # Create creator profile
    creator_profile = CreatorProfile(
        user_id=current_user.id,
        display_name=profile_data.display_name,
        slug=slug,
        bio=profile_data.bio,
        niche=profile_data.niche,
        vertical=CreatorVertical.CONNECT,  # Default to Connect vertical
        language=profile_data.language,
        social_links=profile_data.social_links,
        verification_status=VerificationStatus.APPROVED,  # Auto-approve for MVP
        verified_badge=True
    )
    
    db.add(creator_profile)
    await db.flush() # Flush to get ID for foreign keys
    
    # Create packages if provided
    from app.db.models import ServicePackage
    if profile_data.packages:
        for pkg_data in profile_data.packages:
            pkg = ServicePackage(
                creator_id=creator_profile.id,
                title=pkg_data.title,
                subtitle=pkg_data.subtitle,
                price_inr=pkg_data.price_inr,
                package_type=pkg_data.package_type,
                features=pkg_data.features,
                is_active=True
            )
            db.add(pkg)

    await db.commit()
    
    # Eagerly load packages to avoid MissingGreenlet error
    result = await db.execute(
        select(CreatorProfile)
        .options(selectinload(CreatorProfile.packages))
        .where(CreatorProfile.id == creator_profile.id)
    )
    creator_profile = result.scalar_one()
    
    return creator_profile


@router.get("/profile/{slug}", response_model=CreatorProfileResponse)
async def get_creator_profile(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get public creator profile by slug.
    
    - Returns creator details for discovery
    - Cached for 30 minutes in production
    """
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(CreatorProfile)
        .options(selectinload(CreatorProfile.packages))
        .where(CreatorProfile.slug == slug)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found"
        )
    
    return creator


@router.get("/dashboard", response_model=CreatorDashboard)
async def get_creator_dashboard(
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Get creator dashboard statistics.
    
    - Total earnings, active subscribers, pending messages
    - Revenue charts and growth metrics
    """
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found. Please complete onboarding first."
        )
    
    # Get pending messages count
    result = await db.execute(
        select(func.count(Message.id))
        .where(Message.receiver_id == current_user.id)
        .where(Message.status == MessageStatus.PENDING)
        .where(Message.is_fan_message == True)
    )
    pending_messages = result.scalar() or 0
    
    # Format avg response time
    avg_response_time = None
    if creator.avg_response_time_hours:
        avg_response_time = f"{creator.avg_response_time_hours} hours"
    
    # Mock data for charts (implement actual queries in production)
    return CreatorDashboard(
        total_earnings=float(creator.total_earnings),
        active_subscribers=creator.active_subscribers,
        pending_messages=pending_messages,
        avg_response_time=avg_response_time,
        revenue_chart=[
            {"month": "Jul", "earnings": 0},
            {"month": "Aug", "earnings": 0},
            {"month": "Sep", "earnings": 0},
            {"month": "Oct", "earnings": 0},
            {"month": "Nov", "earnings": 0},
            {"month": "Dec", "earnings": 0},
        ],
        subscriber_growth=[
            {"week": "Week 1", "new": 0, "churned": 0},
            {"week": "Week 2", "new": 0, "churned": 0},
            {"week": "Week 3", "new": 0, "churned": 0},
            {"week": "Week 4", "new": 0, "churned": 0},
        ],
        tier_breakdown=[],
    )


@router.get("/inbox", response_model=List[MessageResponse])
async def get_creator_inbox(
    status_filter: str = "pending",
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Get creator's inbox (pending fan messages).
    
    - Paginated list of messages
    - Filter by status (pending, replied, all)
    """
    query = (
        select(Message)
        .where(Message.receiver_id == current_user.id)
        .where(Message.is_fan_message == True)
        .order_by(Message.created_at.desc())
    )
    
    if status_filter != "all":
        query = query.where(Message.status == status_filter)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return messages


@router.get("/me", response_model=CreatorProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current creator's profile.
    
    - Returns creator profile with packages
    - Used for settings/profile management page
    """
    result = await db.execute(
        select(CreatorProfile)
        .options(selectinload(CreatorProfile.packages))
        .where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found. Please complete onboarding first."
        )
    
    return creator


@router.put("/profile", response_model=CreatorProfileResponse)
async def update_creator_profile(
    profile_data: CreatorOnboard,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Update creator profile.
    
    - Updates profile information (display_name, bio, niche, etc.)
    - Does not update packages (use package endpoints for that)
    - Returns updated profile
    """
    # Get existing profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found. Please complete onboarding first."
        )
    
    # Update profile fields
    creator.display_name = profile_data.display_name
    creator.bio = profile_data.bio
    creator.niche = profile_data.niche
    creator.language = profile_data.language
    creator.social_links = profile_data.social_links
    creator.profile_image_url = profile_data.profile_image_url
    
    await db.commit()
    await db.refresh(creator)
    
    # Reload with packages
    result = await db.execute(
        select(CreatorProfile)
        .options(selectinload(CreatorProfile.packages))
        .where(CreatorProfile.id == creator.id)
    )
    creator = result.scalar_one()
    
    return creator


@router.post("/packages", response_model=ServicePackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package_data: ServicePackageCreate,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new service package.
    
    - Adds package to creator's offerings
    - Returns created package
    """
    from app.db.models import ServicePackage
    
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found."
        )
    
    # Create package
    package = ServicePackage(
        creator_id=creator.id,
        title=package_data.title,
        subtitle=package_data.subtitle,
        price_inr=package_data.price_inr,
        package_type=package_data.package_type,
        features=package_data.features,
        is_active=True
    )
    
    db.add(package)
    await db.commit()
    await db.refresh(package)
    
    return package


@router.put("/packages/{package_id}", response_model=ServicePackageResponse)
async def update_package(
    package_id: UUID,
    package_data: ServicePackageCreate,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing service package.
    
    - Updates package details
    - Only creator who owns the package can update it
    """
    from app.db.models import ServicePackage
    
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found."
        )
    
    # Get package
    result = await db.execute(
        select(ServicePackage)
        .where(ServicePackage.id == package_id)
        .where(ServicePackage.creator_id == creator.id)
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found."
        )
    
    # Update package
    package.title = package_data.title
    package.subtitle = package_data.subtitle
    package.price_inr = package_data.price_inr
    package.package_type = package_data.package_type
    package.features = package_data.features
    
    await db.commit()
    await db.refresh(package)
    
    return package


@router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: UUID,
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete (deactivate) a service package.
    
    - Soft delete by setting is_active=False
    - Only creator who owns the package can delete it
    """
    from app.db.models import ServicePackage
    
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
    )
    creator = result.scalar_one_or_none()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found."
        )
    
    # Get package
    result = await db.execute(
        select(ServicePackage)
        .where(ServicePackage.id == package_id)
        .where(ServicePackage.creator_id == creator.id)
    )
    package = result.scalar_one_or_none()
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found."
        )
    
    # Soft delete
    package.is_active = False
    
    await db.commit()
    
    return None


@router.post("/profile-image", response_model=dict)
async def upload_creator_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload creator profile image.
    Returns the public URL of the uploaded image.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    try:
        from app.utils.azure_storage import azure_storage
        
        file_data = await file.read()
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        
        url = await azure_storage.upload_profile_image(
            file_data=file_data,
            user_id=str(current_user.id),
            file_extension=file_extension
        )
        
        # Also update the profile immediately if it exists
        result = await db.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == current_user.id)
        )
        creator = result.scalar_one_or_none()
        if creator:
            creator.profile_image_url = url
            await db.commit()
            
        return {"profile_image_url": url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )

