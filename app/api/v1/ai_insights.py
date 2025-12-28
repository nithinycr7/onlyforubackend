"""
AI Insights API Endpoints
Provides AI-generated summaries, sentiment analysis, and processing status for bookings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Dict, Any

from app.db.session import get_db
from app.db.models import User, Booking, CreatorProfile
from app.api.deps import get_current_user
from app.services.ai_service import ai_service

router = APIRouter()


@router.get("/bookings/{booking_id}/summary")
async def get_ai_summary(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI-generated summary for a booking.
    
    **CREATOR-ONLY**: Only the creator can view AI summaries. Fans cannot see them.
    
    Returns:
        - summary: Concise 1-2 sentence summary
        - sentiment: Emotional tone (anxious, excited, confused, etc.)
        - stakes: Importance level (high, medium, low)
        - key_points: Array of key points to address
        - processing_status: pending, processing, completed, or failed
    """
    # Get creator profile - ONLY creators can access AI summaries
    creator_result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = creator_result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creators can view AI summaries"
        )
    
    # Get booking
    result = await db.execute(
        select(Booking).filter(
            Booking.id == booking_id,
            Booking.creator_id == creator_profile.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or you are not the creator for this booking"
        )
    
    # Return AI summary data (CREATOR-ONLY)
    return {
        "booking_id": str(booking.id),
        "ai_summary": booking.ai_summary,
        "ai_sentiment": booking.ai_sentiment,
        "ai_stakes": booking.ai_stakes,
        "ai_key_points": booking.ai_key_points,
        "ai_processing_status": booking.ai_processing_status,
        "ai_processing_error": booking.ai_processing_error,
        "detected_languages": booking.detected_languages,
        "ai_summary_language": booking.ai_summary_language
    }


@router.post("/bookings/{booking_id}/regenerate-summary")
async def regenerate_summary(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Regenerate AI summary if creator disagrees with initial summary.
    Only creators can regenerate summaries.
    """
    # Get creator profile
    creator_result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = creator_result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creators can regenerate summaries"
        )
    
    # Get booking
    result = await db.execute(
        select(Booking).filter(
            Booking.id == booking_id,
            Booking.creator_id == creator_profile.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Regenerate AI summary
    try:
        ai_result = await ai_service.process_booking_question(
            question_text=booking.question_text,
            question_audio_url=booking.question_audio_url,
            question_video_url=booking.question_video_url,
            creator_language=creator_profile.language or "en"
        )
        
        # Update booking with new AI insights
        booking.ai_summary = ai_result.get('ai_summary')
        booking.ai_sentiment = ai_result.get('ai_sentiment')
        booking.ai_stakes = ai_result.get('ai_stakes')
        booking.ai_key_points = ai_result.get('ai_key_points')
        booking.ai_processing_status = ai_result.get('ai_processing_status')
        
        await db.commit()
        await db.refresh(booking)
        
        return {
            "message": "AI summary regenerated successfully",
            "ai_summary": booking.ai_summary,
            "ai_sentiment": booking.ai_sentiment,
            "ai_stakes": booking.ai_stakes,
            "ai_key_points": booking.ai_key_points
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate summary: {str(e)}"
        )


@router.get("/bookings/{booking_id}/processing-status")
async def get_processing_status(
    booking_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current AI processing status for a booking.
    Used for polling while AI processes the question.
    
    **CREATOR-ONLY**: Only the creator can check AI processing status.
    
    Returns:
        - status: pending, processing, completed, or failed
        - error: Error message if failed
    """
    # Get creator profile - ONLY creators can access
    creator_result = await db.execute(
        select(CreatorProfile).filter(CreatorProfile.user_id == current_user.id)
    )
    creator_profile = creator_result.scalar_one_or_none()
    
    if not creator_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creators can check AI processing status"
        )
    
    # Get booking
    result = await db.execute(
        select(Booking).filter(
            Booking.id == booking_id,
            Booking.creator_id == creator_profile.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or you are not the creator for this booking"
        )
    
    return {
        "booking_id": str(booking.id),
        "status": booking.ai_processing_status,
        "error": booking.ai_processing_error,
        "has_summary": booking.ai_summary is not None
    }
