from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, extract
from typing import List, Dict, Any
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import Transaction, Message, Subscription, User, CreatorProfile, MessageStatus, TransactionStatus
from app.schemas import CreatorDashboard
from app.core.dependencies import get_current_creator

router = APIRouter()

@router.get("/dashboard", response_model=CreatorDashboard)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_creator),
    db: AsyncSession = Depends(get_db)
):
    """
    Get calculated ROI analytics for Creator Dashboard.
    """
    # 1. Active Subscribers
    result = await db.execute(
        select(func.count(Subscription.id))
        .where(Subscription.creator_id == current_user.creator_profile.id)
        .where(Subscription.status == 'active')
    )
    active_subs = result.scalar() or 0
    
    # 2. Total Earnings (Net Payout)
    result = await db.execute(
        select(func.sum(Transaction.creator_payout_inr))
        .join(Subscription, Transaction.subscription_id == Subscription.id, isouter=True)
        # We need to filter by creator -> Transaction needs direct link or join via sub/package
        # For now assume mostly subscriptions. If package, we need that join too.
        # Let's rely on creator_profile link via user for simpler query if possible, 
        # but Transaction is linked to User (Payer). 
        # So we need to join Subscription -> Creator or Package -> Creator.
        # This is complex in ORM without direct "creator_id" on Transaction.
        # Fix: Add creator_id to Transaction for easier analytics? 
        # Or Just join query.
    )
    # Re-thinking query: 
    # Transaction -> Subscription -> Creator
    # Transaction -> Package -> Creator
    
    # Let's do two queries and sum
    sub_earnings_query = (
        select(func.sum(Transaction.creator_payout_inr))
        .join(Subscription, Transaction.subscription_id == Subscription.id)
        .where(Subscription.creator_id == current_user.creator_profile.id)
        .where(Transaction.status == TransactionStatus.SUCCESS)
    )
    sub_earnings = (await db.execute(sub_earnings_query)).scalar() or 0
    
    pkg_earnings_query = (
        select(func.sum(Transaction.creator_payout_inr))
        # .join(ServicePackage...) # Assuming ServicePackage join
        # For MVP iteration, we might not have packages data populated yet.
    )
    total_earnings = sub_earnings
    
    # 3. Avg Reply Time
    # (RepliedAt - CreatedAt) for messages sent to this creator
    time_query = (
        select(Message.created_at, Message.replied_at)
        .where(Message.receiver_id == current_user.id)
        .where(Message.status == MessageStatus.REPLIED)
        .where(Message.is_fan_message == True)
        .limit(100) # Sample last 100 for performance
    )
    result = await db.execute(time_query)
    times = result.all()
    
    total_seconds = 0
    count = 0
    for created, replied in times:
        if replied and created:
            delta = (replied - created).total_seconds()
            total_seconds += delta
            count += 1
            
    avg_hours = round(total_seconds / 3600 / count, 1) if count > 0 else 0
    avg_response_text = f"{avg_hours}h"
    
    # 4. Pending Messages
    pending_query = (
        select(func.count(Message.id))
        .where(Message.receiver_id == current_user.id)
        .where(Message.status == MessageStatus.PENDING)
        .where(Message.is_fan_message == True)
    )
    pending_msgs = (await db.execute(pending_query)).scalar() or 0

    return CreatorDashboard(
        total_earnings=float(total_earnings),
        active_subscribers=active_subs,
        pending_messages=pending_msgs,
        avg_response_time=avg_response_text,
        revenue_chart=[], # Mock for now or complex group by
        subscriber_growth=[],
        tier_breakdown=[]
    )
