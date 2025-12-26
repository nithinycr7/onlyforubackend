"""
Booking API Endpoints
Handles consultation bookings between fans and creators
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import User, CreatorProfile, ServicePackage, Booking, BookingStatus, FollowUpMessage
from app.schemas import (
    BookingCreate, BookingResponse, BookingWithDetails, RatingSubmit,
    FollowUpMessageCreate, FollowUpMessageResponse, CreatorBookingResponse
)
from app.api.deps import get_current_user
from app.utils.azure_storage import azure_storage

router = APIRouter()


@router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new consultation booking (no payment required for now).
    
    Flow:
    1. Validate service exists
    2. Get creator profile
    3. Calculate expected_response_by based on SLA
    4. Create booking with status='pending_question'
    """
    # Calculate expected response time (Default 48h for now in MVP)
    sla_hours = 48
    expected_response_by = datetime.utcnow() + timedelta(hours=sla_hours)
    
    # Create booking with snapshot data
    new_booking = Booking(
        fan_id=current_user.id,
        creator_id=booking_data.creator_id,
        service_id=booking_data.service_id, # Optional/Nullable now
        service_title=booking_data.service_title,
        service_subtitle=booking_data.service_subtitle,
        status=BookingStatus.PENDING_QUESTION,
        expected_response_by=expected_response_by,
        amount_paid=booking_data.amount_paid,
        follow_ups_remaining=1 # Default 1 for MVP
    )
    
    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)
    
    return new_booking


@router.post("/bookings/{booking_id}/question", response_model=BookingResponse)
async def submit_question(
    booking_id: UUID,
    question_type: str = Form(...),  # 'text', 'audio', 'video'
    question_text: str = Form(None),
    media: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit question for a booking.
    Supports 3 formats: text, audio, video
    
    Args:
        booking_id: Booking ID
        question_type: 'text', 'audio', or 'video'
        question_text: Text question (required for text type, optional for others)
        media: Audio or video file (required for audio/video types)
    
    Flow:
    1. Validate booking belongs to user
    2. Validate question type and required fields
    3. Upload media to Azure Blob (if audio/video)
    4. Update booking with question data
    5. Change status to 'awaiting_response'
    """
    # Validate question_type
    if question_type not in ['text', 'audio', 'video']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_type must be 'text', 'audio', or 'video'"
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
    
    if booking.status != BookingStatus.PENDING_QUESTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question already submitted"
        )
    
    # Handle different question types
    audio_url = None
    video_url = None
    
    if question_type == 'text':
        # Text question - just need text
        if not question_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="question_text is required for text questions"
            )
    
    elif question_type == 'audio':
        # Audio question - need audio file
        if not media:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is required for audio questions"
            )
        
        # Validate file type
        if not media.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )
        
        # Upload to Azure Blob
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
    
    elif question_type == 'video':
        # Video question - need video file
        if not media:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video file is required for video questions"
            )
        
        # Validate file type
        if not media.content_type.startswith('video/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a video file"
            )
        
        # Upload to Azure Blob
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
    
    # Update booking
    booking.question_type = question_type
    booking.question_text = question_text
    booking.question_audio_url = audio_url
    booking.question_video_url = video_url
    booking.question_submitted_at = datetime.utcnow()
    booking.status = BookingStatus.AWAITING_RESPONSE
    
    await db.commit()
    await db.refresh(booking)
    
    return booking


@router.get("/bookings", response_model=List[BookingWithDetails])
async def list_my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all bookings for the current user (fan).
    Returns bookings with service (snapshot) and creator details.
    """
    # Join with CreatorProfile used to get creator details.
    # Service details are now on Booking model directly.
    result = await db.execute(
        select(Booking, CreatorProfile)
        .join(CreatorProfile, Booking.creator_id == CreatorProfile.id)
        .filter(Booking.fan_id == current_user.id)
        .order_by(Booking.created_at.desc())
    )
    
    data = result.all()
    
    # Transform to BookingWithDetails
    bookings_with_details = []
    for booking, creator in data:
        # Generate signed URLs for media
        q_audio = azure_storage.get_signed_url(booking.question_audio_url) if booking.question_audio_url else None
        q_video = azure_storage.get_signed_url(booking.question_video_url) if booking.question_video_url else None
        r_media = azure_storage.get_signed_url(booking.response_media_url) if booking.response_media_url else None

        booking_dict = {
            **booking.__dict__,
            'service_title': booking.service_title or "Consultation",
            'service_subtitle': booking.service_subtitle,
            'creator_display_name': creator.display_name,
            'creator_slug': creator.slug,
            'amount_paid': float(booking.amount_paid or 0),
            'question_audio_url': q_audio,
            'question_video_url': q_video,
            'response_media_url': r_media
        }
        bookings_with_details.append(BookingWithDetails(**booking_dict))
    
    return bookings_with_details


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking_details(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific booking.
    Returns signed URLs for video playback.
    """
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
    
    # Generate signed URLs for media
    if booking.question_audio_url:
        booking.question_audio_url = azure_storage.get_signed_url(booking.question_audio_url)
        
    if booking.question_video_url:
        booking.question_video_url = azure_storage.get_signed_url(booking.question_video_url)
    
    if booking.response_media_url:
        booking.response_media_url = azure_storage.get_signed_url(booking.response_media_url)
    
    return booking


@router.put("/bookings/{booking_id}/rating", response_model=BookingResponse)
async def submit_rating(
    booking_id: UUID,
    rating_data: RatingSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit rating and review for a completed consultation.
    """
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
    
    if booking.status != BookingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate completed consultations"
        )
    
    # Update rating
    booking.fan_rating = rating_data.rating
    booking.fan_review = rating_data.review
    
    await db.commit()
    await db.refresh(booking)
    
    return booking


@router.get("/creator/bookings", response_model=List[CreatorBookingResponse])
async def list_creator_bookings(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all bookings for the current creator.
    Returns bookings with fan details and question data.
    
    Args:
        status: Optional filter by booking status (pending_question, awaiting_response, completed, cancelled)
    """
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found"
        )
    
    # Build query
    query = (
        select(Booking, User)
        .join(User, Booking.fan_id == User.id)
        .filter(Booking.creator_id == creator_profile.id)
    )
    
    # Apply status filter if provided
    if status:
        query = query.filter(Booking.status == status)
    
    # Order by created_at descending (newest first)
    query = query.order_by(Booking.created_at.desc())
    
    result = await db.execute(query)
    data = result.all()
    
    # Transform to CreatorBookingResponse
    bookings_with_fan_details = []
    for booking, fan in data:
        # Generate signed URLs for media
        q_audio = azure_storage.get_signed_url(booking.question_audio_url) if booking.question_audio_url else None
        q_video = azure_storage.get_signed_url(booking.question_video_url) if booking.question_video_url else None
        r_media = azure_storage.get_signed_url(booking.response_media_url) if booking.response_media_url else None

        booking_dict = {
            'id': booking.id,
            'fan_id': fan.id,
            'fan_name': fan.full_name,
            'fan_email': fan.email,
            'fan_profile_image_url': fan.profile_image_url,
            'service_title': booking.service_title,
            'service_subtitle': booking.service_subtitle,
            'question_type': booking.question_type,
            'question_text': booking.question_text,
            'question_audio_url': q_audio,
            'question_video_url': q_video,
            'question_submitted_at': booking.question_submitted_at,
            'response_media_url': r_media,
            'response_type': booking.response_type,
            'response_submitted_at': booking.response_submitted_at,
            'status': booking.status,
            'expected_response_by': booking.expected_response_by,
            'sla_met': booking.sla_met,
            'amount_paid': float(booking.amount_paid or 0),
            'created_at': booking.created_at,
            'updated_at': booking.updated_at
        }
        bookings_with_fan_details.append(CreatorBookingResponse(**booking_dict))
    
    return bookings_with_fan_details


@router.post("/bookings/{booking_id}/response", response_model=BookingResponse)
async def submit_creator_response(
    booking_id: UUID,
    response_type: str = Form(...),  # 'voice' or 'video'
    media: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit creator response to a booking.
    Uploads media to Azure Blob and updates booking status to COMPLETED.
    
    Args:
        booking_id: Booking ID
        response_type: 'voice' or 'video'
        media: Audio or video file
    
    Flow:
        1. Validate booking belongs to creator
        2. Validate booking is in AWAITING_RESPONSE status
        3. Upload media to Azure Blob
        4. Update booking with response data
        5. Change status to COMPLETED
    """
    # Validate response_type
    if response_type not in ['voice', 'video']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="response_type must be 'voice' or 'video'"
        )
    
    # Get creator profile
    result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found"
        )
    
    # Get booking
    result = await db.execute(
        select(Booking).filter(
            and_(
                Booking.id == booking_id,
                Booking.creator_id == creator_profile.id
            )
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    if booking.status != BookingStatus.AWAITING_RESPONSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot respond to booking with status: {booking.status}"
        )
    
    # Validate file type
    if response_type == 'voice':
        if not media.content_type or not media.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file for voice responses"
            )
    elif response_type == 'video':
        if not media.content_type or not media.content_type.startswith('video/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a video file for video responses"
            )
    
    # Upload to Azure Blob
    try:
        media_data = await media.read()
        file_extension = media.filename.split('.')[-1] if '.' in media.filename else ('mp3' if response_type == 'voice' else 'mp4')
        
        if response_type == 'voice':
            response_url = await azure_storage.upload_response_audio(
                file_data=media_data,
                booking_id=str(booking_id),
                file_extension=file_extension
            )
        else:  # video
            response_url = await azure_storage.upload_response_video(
                file_data=media_data,
                booking_id=str(booking_id),
                file_extension=file_extension
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload response media: {str(e)}"
        )
    
    # Update booking
    booking.response_media_url = response_url
    booking.response_type = response_type
    booking.response_submitted_at = datetime.utcnow()
    booking.status = BookingStatus.COMPLETED
    
    # Check if SLA was met (handle timezone-aware comparison)
    if booking.expected_response_by:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        # Make expected_response_by timezone-aware if it isn't
        expected_by = booking.expected_response_by
        if expected_by.tzinfo is None:
            expected_by = expected_by.replace(tzinfo=timezone.utc)
        booking.sla_met = now_utc <= expected_by
    
    await db.commit()
    await db.refresh(booking)
    
    return booking

