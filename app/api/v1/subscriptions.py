from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import date, timedelta

from app.db.session import get_db
from app.db.models import Subscription, SubscriptionTier, FanClub, CreatorProfile, SubscriptionStatus
from app.schemas import SubscriptionCreate, SubscriptionResponse
from app.core.dependencies import get_current_fan

router = APIRouter()


@router.post("/subscribe", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user = Depends(get_current_fan),
    db: AsyncSession = Depends(get_db)
):
    """
    Create new subscription.
    
    - Creates subscription record
    - Returns payment order details (Razorpay integration)
    - In development: Auto-activates subscription
    """
    # Get tier details
    result = await db.execute(
        select(SubscriptionTier, FanClub, CreatorProfile)
        .join(FanClub, SubscriptionTier.club_id == FanClub.id)
        .join(CreatorProfile, FanClub.creator_id == CreatorProfile.id)
        .where(SubscriptionTier.id == subscription_data.tier_id)
    )
    tier_data = result.first()
    
    if not tier_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription tier not found"
        )
    
    tier, club, creator = tier_data
    
    # Check if already subscribed to this club
    result = await db.execute(
        select(Subscription)
        .where(Subscription.fan_id == current_user.id)
        .where(Subscription.club_id == club.id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    existing_subscription = result.scalar_one_or_none()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already subscribed to this club"
        )
    
    # Create subscription
    today = date.today()
    subscription = Subscription(
        fan_id=current_user.id,
        tier_id=tier.id,
        club_id=club.id,
        creator_id=creator.id,
        status=SubscriptionStatus.ACTIVE,  # Auto-activate in development
        current_period_start=today,
        current_period_end=today + timedelta(days=30),
        next_billing_date=today + timedelta(days=30),
    )
    
    db.add(subscription)
    
    # Update club member count
    club.total_members += 1
    creator.active_subscribers += 1
    
    await db.commit()
    await db.refresh(subscription)
    
    # In production: Create Razorpay order and return order_id
    # razorpay_order = razorpay_client.order.create({
    #     "amount": int(tier.price_inr * 100),  # Amount in paise
    #     "currency": "INR",
    #     "receipt": str(subscription.id),
    # })
    
    return {
        "subscription_id": str(subscription.id),
        "status": "active",  # In dev, auto-activated
        "message": "Subscription created successfully (auto-activated in development)",
        # In production, return:
        # "razorpay_order_id": razorpay_order["id"],
        # "amount": tier.price_inr,
        # "currency": "INR",
    }


@router.get("/my-subscriptions", response_model=List[dict])
async def get_my_subscriptions(
    current_user = Depends(get_current_fan),
    db: AsyncSession = Depends(get_db)
):
    """
    Get fan's active subscriptions.
    
    - Returns subscription details with creator info
    - Shows usage stats (messages sent this period)
    """
    result = await db.execute(
        select(Subscription, SubscriptionTier, FanClub, CreatorProfile)
        .join(SubscriptionTier, Subscription.tier_id == SubscriptionTier.id)
        .join(FanClub, Subscription.club_id == FanClub.id)
        .join(CreatorProfile, Subscription.creator_id == CreatorProfile.id)
        .where(Subscription.fan_id == current_user.id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .order_by(Subscription.created_at.desc())
    )
    subscriptions_data = result.all()
    
    response = []
    for subscription, tier, club, creator in subscriptions_data:
        response.append({
            "subscription_id": str(subscription.id),
            "status": subscription.status,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": subscription.current_period_end.isoformat(),
            "next_billing_date": subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
            "messages_sent_this_period": subscription.messages_sent_this_period,
            "messages_remaining": tier.max_messages_per_month - subscription.messages_sent_this_period,
            "tier": {
                "tier_name": tier.tier_name,
                "tier_type": tier.tier_type,
                "price_inr": float(tier.price_inr),
                "max_messages_per_month": tier.max_messages_per_month,
            },
            "club": {
                "club_name": club.club_name,
                "slug": club.slug,
            },
            "creator": {
                "display_name": creator.display_name,
                "slug": creator.slug,
                "profile_image_url": creator.user.profile_image_url if creator.user else None,
            }
        })
    
    return response


@router.post("/cancel/{subscription_id}", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    subscription_id: str,
    current_user = Depends(get_current_fan),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel subscription.
    
    - Sets status to cancelled
    - Subscription remains active until period end
    - No refund (service already delivered)
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .where(Subscription.fan_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if subscription.status == SubscriptionStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription already cancelled"
        )
    
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.next_billing_date = None
    
    await db.commit()
    
    return {
        "message": "Subscription cancelled successfully",
        "active_until": subscription.current_period_end.isoformat(),
    }
