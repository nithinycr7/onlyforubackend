"""
Follow-up Message Endpoints
Handles conversation threads within consultations
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from uuid import UUID
from datetime import datetime

from app.db.session import get_db
from app.db.models import User, Booking, BookingStatus, FollowUpMessage
from app.schemas import FollowUpMessageResponse
from app.api.deps import get_current_user
from app.utils.azure_storage import azure_storage

router = APIRouter()


@router.post("/bookings/{booking_id}/follow-up", response_model=FollowUpMessageResponse)
async def submit_follow_up(
    booking_id: UUID,
    message_type: str,  # 'text', 'audio', 'video'
    text_content: str = None,
    media: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a follow-up message in a consultation.
    
    Flow:
    1. Validate booking belongs to user
    2. Check follow_ups_remaining > 0
    3. Upload media if needed
    4. Create follow-up message
    5. Decrement follow_ups_remaining
    6. Change status back to 'awaiting_response'
    """
    # Validate message_type
    if message_type not in ['text', 'audio', 'video']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message_type must be 'text', 'audio', or 'video'"
        )
    
    # Get booking
    result = await db.execute(
        select(Booking).filter(
            and_(
                Booking.id == booking_id,
                Booking.fan_id == current_user.id
            )
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if follow-ups are allowed
    if booking.follow_ups_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No follow-ups remaining for this booking"
        )
    
    # Must be completed before follow-up
    if booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only submit follow-ups after creator responds"
        )
    
    # Handle media upload
    audio_url = None
    video_url = None
    
    if message_type == 'text':
        if not text_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="text_content is required for text messages"
            )
    
    elif message_type == 'audio':
        if not media:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is required for audio messages"
            )
        
        if not media.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )
        
        try:
            audio_data = await media.read()
            file_extension = media.filename.split('.')[-1] if '.' in media.filename else 'mp3'
            audio_url = await azure_storage.upload_question_audio(
                file_data=audio_data,
                booking_id=str(booking_id),
                file_extension=file_extension
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload audio: {str(e)}"
            )
    
    elif message_type == 'video':
        if not media:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video file is required for video messages"
            )
        
        if not media.content_type.startswith('video/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a video file"
            )
        
        try:
            video_data = await media.read()
            file_extension = media.filename.split('.')[-1] if '.' in media.filename else 'mp4'
            video_url = await azure_storage.upload_question_video(
                file_data=video_data,
                booking_id=str(booking_id),
                file_extension=file_extension
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload video: {str(e)}"
            )
    
    # Create follow-up message
    follow_up = FollowUpMessage(
        booking_id=booking_id,
        sender_type='fan',
        message_type=message_type,
        text_content=text_content,
        audio_url=audio_url,
        video_url=video_url
    )
    
    db.add(follow_up)
    
    # Update booking
    booking.follow_ups_remaining -= 1
    booking.status = BookingStatus.AWAITING_RESPONSE
    
    await db.commit()
    await db.refresh(follow_up)
    
    return follow_up


@router.get("/bookings/{booking_id}/messages", response_model=List[FollowUpMessageResponse])
async def get_conversation_thread(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the complete conversation thread for a booking.
    Returns all follow-up messages in chronological order.
    """
    # Verify booking belongs to user
    result = await db.execute(
        select(Booking).filter(
            and_(
                Booking.id == booking_id,
                Booking.fan_id == current_user.id
            )
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Get all follow-up messages
    result = await db.execute(
        select(FollowUpMessage)
        .filter(FollowUpMessage.booking_id == booking_id)
        .order_by(FollowUpMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    # Generate signed URLs for media
    for message in messages:
        if message.audio_url:
            message.audio_url = azure_storage.get_signed_url(message.audio_url)
        if message.video_url:
            message.video_url = azure_storage.get_signed_url(message.video_url)
    
    return messages
