import asyncio
import os
import json
import sys

# Production database URL
os.environ["DATABASE_URL"] = "postgresql+asyncpg://onlyforu_user:aXeF5PGF6UlRMNgkFKT1CtEILdSkkbU0@dpg-d579uvbuibrs73a1td10-a.singapore-postgres.render.com/onlyforu_db"

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Booking

async def check_transcription(booking_id=None):
    async with AsyncSessionLocal() as db:
        if booking_id:
            from uuid import UUID
            try:
                bid_uuid = UUID(booking_id)
                result = await db.execute(select(Booking).where(Booking.id == bid_uuid))
            except ValueError:
                print(f"❌ Invalid UUID format: {booking_id}")
                return
        else:
            # Find latest booking with audio
            result = await db.execute(
                select(Booking)
                .where(Booking.question_audio_urls.isnot(None))
                .order_by(Booking.created_at.desc())
                .limit(1)
            )
        booking = result.scalar_one_or_none()
        
        if not booking:
            print(f"❌ No booking found{' with ID ' + booking_id if booking_id else ''}")
            return
        
        print(f"\n{'='*70}")
        print(f"📋 Booking Details: {booking.id}")
        print(f"{'='*70}")
        print(f"Created: {booking.created_at}")
        print(f"Question Text: {booking.question_text}")
        print(f"Audio URLs: {booking.question_audio_urls}")
        
        print(f"\n--- AI Status ---")
        print(f"Status: {booking.ai_processing_status}")
        print(f"Error: {booking.ai_processing_error}")
        
        print(f"\n--- Transcription Results ---")
        print(f"Detected Languages: {json.dumps(booking.detected_languages, indent=2)}")
        print(f"Transcriptions: {json.dumps(booking.transcriptions, indent=2)}")
        print(f"Translations: {json.dumps(booking.translations, indent=2)}")
        
        print(f"\n--- AI Summary ---")
        print(f"Summary: {booking.ai_summary}")
        print(f"Sentiment: {booking.ai_sentiment}")
        print(f"Stakes: {booking.ai_stakes}")
        print(f"Key Points: {json.dumps(booking.ai_key_points, indent=2)}")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    bid = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(check_transcription(bid))
