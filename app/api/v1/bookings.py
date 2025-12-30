"""
Booking API Endpoints
Handles consultation bookings between fans and creators
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
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
from app.core.config import settings

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
    question_type: str = Form(...),  # 'text', 'audio', 'video', 'image', 'multi'
    question_text: str = Form(None),
    
    # Multi-format support: Accept multiple files per type
    audio_files: List[UploadFile] = File(None),
    video_files: List[UploadFile] = File(None),
    image_files: List[UploadFile] = File(None),
    
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit question for a booking with multi-format support.
    Supports: text, audio, video, image, or multi (combination)
    
    Args:
        booking_id: Booking ID
        question_type: 'text', 'audio', 'video', 'image', or 'multi'
        question_text: Text question (optional)
        audio_files: List of audio files (max 3)
        video_files: List of video files (max 2)
        image_files: List of image files (max 5)
    
    Flow:
    1. Validate booking belongs to user
    2. Validate question type and files
    3. Upload all media to Azure Blob
    4. Update booking with question data
    5. Trigger AI processing
    6. Change status to 'awaiting_response'
    """
    # Validate question_type
    if question_type not in ['text', 'audio', 'video', 'image', 'multi']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_type must be 'text', 'audio', 'video', 'image', or 'multi'"
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
    
    # File limits
    MAX_AUDIO_FILES = 3
    MAX_VIDEO_FILES = 2
    MAX_IMAGE_FILES = 5
    
    # Validate file counts
    if audio_files and len(audio_files) > MAX_AUDIO_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_AUDIO_FILES} audio files allowed"
        )
    
    if video_files and len(video_files) > MAX_VIDEO_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_VIDEO_FILES} video files allowed"
        )
    
    if image_files and len(image_files) > MAX_IMAGE_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_IMAGE_FILES} image files allowed"
        )
    
    # Upload all media files
    audio_urls = []
    video_urls = []
    image_urls = []
    
    # Upload audio files
    if audio_files:
        for idx, audio_file in enumerate(audio_files):
            if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {audio_file.filename} must be an audio file"
                )
            
            try:
                audio_data = await audio_file.read()
                file_extension = audio_file.filename.split('.')[-1] if '.' in audio_file.filename else 'mp3'
                audio_url = await azure_storage.upload_question_audio(
                    file_data=audio_data,
                    booking_id=f"{booking_id}_audio_{idx}",
                    file_extension=file_extension
                )
                audio_urls.append(audio_url)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload audio file {idx+1}: {str(e)}"
                )
    
    # Upload video files
    if video_files:
        for idx, video_file in enumerate(video_files):
            if not video_file.content_type or not video_file.content_type.startswith('video/'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {video_file.filename} must be a video file"
                )
            
            try:
                video_data = await video_file.read()
                file_extension = video_file.filename.split('.')[-1] if '.' in video_file.filename else 'mp4'
                video_url = await azure_storage.upload_question_video(
                    file_data=video_data,
                    booking_id=f"{booking_id}_video_{idx}",
                    file_extension=file_extension
                )
                video_urls.append(video_url)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload video file {idx+1}: {str(e)}"
                )
    
    # Upload image files
    if image_files:
        for idx, image_file in enumerate(image_files):
            if not image_file.content_type or not image_file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {image_file.filename} must be an image file"
                )
            
            try:
                image_data = await image_file.read()
                file_extension = image_file.filename.split('.')[-1] if '.' in image_file.filename else 'jpg'
                # Reuse upload_question_video for now (same blob container)
                image_url = await azure_storage.upload_question_video(
                    file_data=image_data,
                    booking_id=f"{booking_id}_image_{idx}",
                    file_extension=file_extension
                )
                image_urls.append(image_url)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload image file {idx+1}: {str(e)}"
                )
    
    # Update booking
    booking.question_type = question_type
    booking.question_text = question_text
    booking.question_audio_urls = audio_urls if audio_urls else None
    booking.question_video_urls = video_urls if video_urls else None
    booking.question_image_urls = image_urls if image_urls else None
    booking.question_submitted_at = datetime.utcnow()
    booking.status = BookingStatus.AWAITING_RESPONSE
    
    await db.commit()
    await db.refresh(booking)
    
    # Trigger AI processing asynchronously (Phase 1: AI Integration)
    if settings.enable_ai_summaries:
        try:
            import asyncio
            from app.utils.ai_utils import process_ai_insights_internal
            
            # Set initial status to processing
            booking.ai_processing_status = 'processing'
            await db.commit()
            await db.refresh(booking)  # Refresh again to load all attributes before task
            
            # Use asyncio.create_task instead of BackgroundTasks for async DB access
            asyncio.create_task(process_ai_insights_internal(booking.id))
            print(f"DEBUG: AI processing task created for booking {booking.id}")
            
        except Exception as e:
            # Log error but don't fail the request
            print(f"ERROR: Failed to start background AI processing for booking {booking.id}: {str(e)}")
    
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
        # Generate signed URLs for media lists
        q_audio = [azure_storage.get_signed_url(url) for url in booking.question_audio_urls] if booking.question_audio_urls else None
        q_video = [azure_storage.get_signed_url(url) for url in booking.question_video_urls] if booking.question_video_urls else None
        q_images = [azure_storage.get_signed_url(url) for url in booking.question_image_urls] if booking.question_image_urls else None
        r_media = azure_storage.get_signed_url(booking.response_media_url) if booking.response_media_url else None

        booking_dict = {
            **booking.__dict__,
            'service_title': booking.service_title or "Consultation",
            'service_subtitle': booking.service_subtitle,
            'creator_display_name': creator.display_name,
            'creator_slug': creator.slug,
            'amount_paid': float(booking.amount_paid or 0),
            'question_audio_urls': q_audio,
            'question_video_urls': q_video,
            'question_image_urls': q_images,
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
        select(Booking, CreatorProfile).join(
            CreatorProfile, Booking.creator_id == CreatorProfile.id
        ).filter(
            and_(
                Booking.id == booking_id,
                Booking.fan_id == current_user.id
            )
        )
    )
    row = result.first()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    booking, creator_profile = row
    
    # Generate signed URLs for media lists
    if booking.question_audio_urls:
        booking.question_audio_urls = [azure_storage.get_signed_url(url) for url in booking.question_audio_urls]
        
    if booking.question_video_urls:
        booking.question_video_urls = [azure_storage.get_signed_url(url) for url in booking.question_video_urls]
        
    if booking.question_image_urls:
        booking.question_image_urls = [azure_storage.get_signed_url(url) for url in booking.question_image_urls]
    
    if booking.response_media_url:
        booking.response_media_url = azure_storage.get_signed_url(booking.response_media_url)
    
    # Populate creator information
    booking.creator_display_name = creator_profile.display_name
    booking.creator_profile_image = azure_storage.get_signed_url(creator_profile.profile_image_url) if creator_profile.profile_image_url else None
    
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
        # Generate signed URLs for media lists
        q_audio = [azure_storage.get_signed_url(url) for url in booking.question_audio_urls] if booking.question_audio_urls else None
        q_video = [azure_storage.get_signed_url(url) for url in booking.question_video_urls] if booking.question_video_urls else None
        q_images = [azure_storage.get_signed_url(url) for url in booking.question_image_urls] if booking.question_image_urls else None
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
            'question_audio_urls': q_audio,
            'question_video_urls': q_video,
            'question_image_urls': q_images,
            'question_submitted_at': booking.question_submitted_at,
            'response_text': booking.response_text,
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
    response_text: Optional[str] = Form(None),
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
    booking.response_text = response_text
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

