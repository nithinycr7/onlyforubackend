from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.db.models import Message, Subscription, SubscriptionStatus, MessageStatus, User
from app.schemas import MessageCreate, MessageResponse, ThreadResponse
from app.core.dependencies import get_current_user

router = APIRouter()


@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fan sends message to creator.
    
    - Validates subscription is active
    - Checks monthly message limit
    - Creates pending message
    """
    # Get subscription
    result = await db.execute(
        select(Subscription)
        .where(Subscription.id == message_data.subscription_id)
        .where(Subscription.fan_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    if subscription.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not active"
        )
    
    # Get tier to check message limit
    tier = subscription.tier
    
    if subscription.messages_sent_this_period >= tier.max_messages_per_month:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly message limit reached ({tier.max_messages_per_month} messages)"
        )
    
    # Get creator user ID
    creator_profile = subscription.tier.club.creator
    creator_user_id = creator_profile.user_id
    
    # Create message
    message = Message(
        subscription_id=subscription.id,
        sender_id=current_user.id,
        receiver_id=creator_user_id,
        message_type=message_data.message_type,
        content=message_data.content,
        media_url=message_data.media_url,
        media_duration_secs=message_data.media_duration_secs,
        status=MessageStatus.PENDING,
        is_fan_message=True,
    )
    
    db.add(message)
    
    # Increment message counter
    subscription.messages_sent_this_period += 1
    
    await db.commit()
    await db.refresh(message)
    
    # Real-time Notification
    from app.core.websockets import manager
    from app.schemas import MessageResponse

    # Convert to schema for serialization
    # Note: We need to serialize appropriately. Pydantic .model_dump() is easy.
    # But created_at might be datetime.
    
    msg_data = MessageResponse.model_validate(message).model_dump(mode='json')
    
    # Send to Receiver (Creator)
    await manager.send_personal_message({
        "type": "message_new",
        "data": msg_data
    }, str(creator_user_id))
    
    return message


@router.get("/thread/{subscription_id}", response_model=ThreadResponse)
async def get_message_thread(
    subscription_id: str,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full message thread for a subscription.
    
    - Returns all messages (fan queries + creator replies)
    - Paginated, ordered by created_at
    """
    # Verify user has access to this subscription
    result = await db.execute(
        select(Subscription)
        .where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    # Check if user is either the fan or the creator
    if current_user.id != subscription.fan_id and current_user.id != subscription.tier.club.creator.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.subscription_id == subscription_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()
    
    messages = result.scalars().all()
    
    # Construct Thread Response
    title = subscription.tier.title if subscription.tier else "Chat"
    subtitle = subscription.tier.club.creator.display_name if subscription.tier and subscription.tier.club else "Creator"
    
    # For creator view, subtitle might be fan name
    if current_user.id == subscription.tier.club.creator.user_id:
        # Fetch fan name
        result = await db.execute(select(User).where(User.id == subscription.fan_id))
        fan = result.scalar_one_or_none()
        subtitle = fan.full_name if fan else "Fan"
        title = f"{title} (Fan: {subtitle})"

    from app.schemas import ThreadResponse
    return ThreadResponse(
        subscription_id=str(subscription.id),
        title=title,
        subtitle=subtitle,
        status=subscription.status,
        messages=messages,
        current_user_id=str(current_user.id)
    )


@router.post("/reply/{message_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def reply_to_message(
    message_id: str,
    reply_content: str = None,
    reply_media_url: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creator replies to fan message.
    
    - Creates reply message
    - Updates original message status to 'replied'
    - Sends notification to fan
    """
    # Get original message
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id)
        .where(Message.receiver_id == current_user.id)
        .where(Message.is_fan_message == True)
    )
    original_message = result.scalar_one_or_none()
    
    if not original_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied"
        )
    
    if original_message.status == MessageStatus.REPLIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message already replied"
        )
    
    # Create reply message
    reply_message = Message(
        subscription_id=original_message.subscription_id,
        sender_id=current_user.id,
        receiver_id=original_message.sender_id,
        message_type=original_message.message_type,
        content=reply_content,
        media_url=reply_media_url,
        status=MessageStatus.REPLIED,
        is_fan_message=False,
    )
    
    db.add(reply_message)
    
    # Update original message
    original_message.status = MessageStatus.REPLIED
    from datetime import datetime
    original_message.replied_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(reply_message)
    
    # Real-time Notification
    from app.core.websockets import manager
    from app.schemas import MessageResponse
    
    msg_data = MessageResponse.model_validate(reply_message).model_dump(mode='json')
    
    # Send to Receiver (Fan)
    await manager.send_personal_message({
        "type": "message_new",
        "data": msg_data
    }, str(original_message.sender_id))
    
    return reply_message
