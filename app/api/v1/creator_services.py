"""
Creator Service Management API Endpoints
Handles CRUD operations for creator profiles and consultation services
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.db.models import User, CreatorProfile, ServicePackage
from app.schemas import ServicePackageCreate, ServicePackageUpdate, ServicePackageResponse
from app.api.deps import get_current_user, get_current_creator

router = APIRouter()


# ============= Service Management Endpoints =============

@router.post("/services", response_model=ServicePackageResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: ServicePackageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_creator)
):
    """
    Create a new consultation service.
    Only accessible by creators.
    """
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found. Please complete onboarding first."
        )
    
    # Create service package
    new_service = ServicePackage(
        creator_id=creator_profile.id,
        **service_data.dict()
    )
    
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)
    
    return new_service


@router.get("/services", response_model=List[ServicePackageResponse])
async def list_creator_services(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_creator)
):
    """
    List all services for the current creator.
    """
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found"
        )
    
    result = await db.execute(
        select(ServicePackage)
        .filter(ServicePackage.creator_id == creator_profile.id)
        .order_by(ServicePackage.display_order, ServicePackage.created_at)
    )
    services = result.scalars().all()
    
    return services


@router.get("/services/{service_id}", response_model=ServicePackageResponse)
async def get_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_creator)
):
    """
    Get a specific service by ID.
    """
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    result = await db.execute(
        select(ServicePackage).filter(
            and_(
                ServicePackage.id == service_id,
                ServicePackage.creator_id == creator_profile.id
            )
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    return service


@router.put("/services/{service_id}", response_model=ServicePackageResponse)
async def update_service(
    service_id: UUID,
    service_data: ServicePackageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_creator)
):
    """
    Update an existing service.
    """
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    result = await db.execute(
        select(ServicePackage).filter(
            and_(
                ServicePackage.id == service_id,
                ServicePackage.creator_id == creator_profile.id
            )
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Update only provided fields
    update_data = service_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)
    
    await db.commit()
    await db.refresh(service)
    
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_creator)
):
    """
    Delete a service (soft delete by setting is_active=False).
    """
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    result = await db.execute(
        select(ServicePackage).filter(
            and_(
                ServicePackage.id == service_id,
                ServicePackage.creator_id == creator_profile.id
            )
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Soft delete
    service.is_active = False
    await db.commit()
    
    return None


# ============= Public Service Discovery =============

@router.get("/creators/{slug}/services", response_model=List[ServicePackageResponse])
async def get_creator_services_public(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all active services for a creator (public endpoint).
    """
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.slug == slug)
    )
    creator_profile = result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found"
        )
    
    result = await db.execute(
        select(ServicePackage)
        .filter(
            and_(
                ServicePackage.creator_id == creator_profile.id,
                ServicePackage.is_active == True
            )
        )
        .order_by(ServicePackage.display_order, ServicePackage.price_inr)
    )
    services = result.scalars().all()
    
    return services
