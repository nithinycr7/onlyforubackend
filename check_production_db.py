import asyncio
import os

# Production database URL
os.environ["DATABASE_URL"] = "postgresql+asyncpg://onlyforu_user:aXeF5PGF6UlRMNgkFKT1CtEILdSkkbU0@dpg-d579uvbuibrs73a1td10-a.singapore-postgres.render.com/onlyforu_db"

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Booking

async def check_production_booking():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).order_by(Booking.created_at.desc()).limit(1)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            print("No bookings found.")
            return
        
        print(f"\n=== Latest Production Booking ===")
        print(f"Booking ID: {booking.id}")
        print(f"Created: {booking.created_at}")
        print(f"\n--- Question Data ---")
        print(f"Question Text: {booking.question_text}")
        print(f"Question Type: {booking.question_type}")
        print(f"Audio URLs: {booking.question_audio_urls}")
        print(f"Video URLs: {booking.question_video_urls}")
        print(f"\n--- AI Processing ---")
        print(f"AI Status: {booking.ai_processing_status}")
        print(f"AI Error: {booking.ai_processing_error}")
        print(f"\n--- AI Results ---")
        print(f"AI Summary: {booking.ai_summary}")
        print(f"Sentiment: {booking.ai_sentiment}")
        print(f"Stakes: {booking.ai_stakes}")
        print(f"Key Points: {booking.ai_key_points}")
        print(f"\n--- Multilingual Data ---")
        print(f"Detected Languages: {booking.detected_languages}")
        print(f"Transcriptions: {booking.transcriptions}")
        print(f"Translations: {booking.translations}")

if __name__ == "__main__":
    asyncio.run(check_production_booking())
