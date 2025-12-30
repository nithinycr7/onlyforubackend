import logging
from uuid import UUID
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Booking, CreatorProfile
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

async def process_ai_insights_internal(booking_id: UUID):
    """
    Background task to process AI insights for a booking.
    This function handles its own database session since it runs after the request is finished.
    """
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"Starting background AI processing for booking {booking_id}")
            
            # 1. Get booking
            result = await db.execute(select(Booking).filter(Booking.id == booking_id))
            booking = result.scalar_one_or_none()
            
            if not booking:
                logger.error(f"Booking {booking_id} not found for AI processing")
                return
            
            # 2. Get creator info for language preference
            creator_result = await db.execute(
                select(CreatorProfile).filter(CreatorProfile.id == booking.creator_id)
            )
            creator = creator_result.scalar_one_or_none()
            creator_language = creator.language if creator else "en"
            
            # 3. Generate signed URLs for media (required for private blob access)
            from app.utils.azure_storage import azure_storage
            
            signed_audio_urls = []
            if booking.question_audio_urls:
                signed_audio_urls = [
                    azure_storage.get_signed_url(url) for url in booking.question_audio_urls
                ]
            
            signed_video_urls = []
            if booking.question_video_urls:
                signed_video_urls = [
                    azure_storage.get_signed_url(url) for url in booking.question_video_urls
                ]
            
            signed_image_urls = []
            if booking.question_image_urls:
                signed_image_urls = [
                    azure_storage.get_signed_url(url) for url in booking.question_image_urls
                ]
            
            # 4. Call AI service with signed URLs
            ai_service = get_ai_service()
            ai_result = await ai_service.process_booking_question(
                question_text=booking.question_text,
                question_audio_urls=signed_audio_urls,
                question_video_urls=signed_video_urls,
                question_image_urls=signed_image_urls,
                creator_language=creator_language or "en"
            )
            
            # 5. Update booking with results
            booking.ai_summary = ai_result.get('ai_summary')
            booking.ai_summary_language = ai_result.get('ai_summary_language')
            booking.ai_sentiment = ai_result.get('ai_sentiment')
            booking.ai_stakes = ai_result.get('ai_stakes')
            booking.ai_key_points = ai_result.get('ai_key_points')
            booking.detected_languages = ai_result.get('detected_languages')
            booking.transcriptions = ai_result.get('transcriptions')
            booking.translations = ai_result.get('translations')
            booking.ai_processing_status = ai_result.get('ai_processing_status', 'completed')
            booking.ai_processing_error = ai_result.get('ai_processing_error')
            
            await db.commit()
            logger.info(f"AI processing completed for booking {booking_id}")
            
        except Exception as e:
            logger.error(f"AI processing failed for booking {booking_id}: {str(e)}")
            # Attempt to save error state
            try:
                booking.ai_processing_status = 'failed'
                booking.ai_processing_error = str(e)
                await db.commit()
            except:
                pass
