import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Fix database URL for async
db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgresql://"):
    os.environ["DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+asyncpg://")

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Booking

async def check_latest_booking():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking).order_by(Booking.created_at.desc()).limit(1)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            print("No bookings found.")
            return
        
        print(f"\n=== Latest Booking ===")
        print(f"Booking ID: {booking.id}")
        print(f"\nQuestion Text: {booking.question_text}")
        print(f"\nAudio URLs: {booking.question_audio_urls}")
        print(f"\nAI Summary: {booking.ai_summary}")
        print(f"\nTranscriptions: {booking.transcriptions}")
        print(f"\nTranslations: {booking.translations}")
        print(f"\nDetected Languages: {booking.detected_languages}")
        print(f"\nAI Processing Status: {booking.ai_processing_status}")
        print(f"\nAI Processing Error: {booking.ai_processing_error}")

if __name__ == "__main__":
    asyncio.run(check_latest_booking())
