import asyncio
import os
from sqlalchemy import text
from app.db.session import engine

async def add_columns():
    async with engine.begin() as conn:
        print("Checking if columns exist...")
        # Add columns if they don't exist
        try:
            await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50);"))
            await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS razorpay_order_id VARCHAR(100);"))
            await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS razorpay_payment_id VARCHAR(100);"))
            await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS razorpay_signature VARCHAR(200);"))
            print("Columns added successfully!")
        except Exception as e:
            print(f"Error adding columns: {e}")

if __name__ == "__main__":
    asyncio.run(add_columns())
