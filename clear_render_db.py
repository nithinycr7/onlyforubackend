import asyncio
import os
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

# Production database URL from check_production_db.py
os.environ["DATABASE_URL"] = "postgresql+asyncpg://onlyforu_user:aXeF5PGF6UlRMNgkFKT1CtEILdSkkbU0@dpg-d579uvbuibrs73a1td10-a.singapore-postgres.render.com/onlyforu_db"

TABLES_TO_CLEAR = [
    "follow_up_messages",
    "bookings",
    "content_reports",
    "referrals",
    "transactions",
    "content_drops",
    "messages",
    "subscriptions",
    "subscription_tiers",
    "fan_clubs",
    "service_packages",
    "service_templates",
    "creator_profiles",
    "users"
]

import sys

async def clear_production_data():
    if len(sys.argv) < 2 or sys.argv[1] != "--confirm-delete":
        print("⚠️ WARNING: This will permanently delete ALL data from the production database on Render.")
        print("To confirm, run with: python clear_render_db.py --confirm-delete")
        return

    async with AsyncSessionLocal() as db:
        print("Starting cleanup...")
        for table in TABLES_TO_CLEAR:
            try:
                print(f"Clearing table: {table}")
                # We use CASCADE to handle foreign key constraints
                await db.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
            except Exception as e:
                print(f"Error clearing {table}: {e}")
        
        await db.commit()
        print("\n✅ Production database cleared successfully.")

if __name__ == "__main__":
    asyncio.run(clear_production_data())
