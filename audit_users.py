import asyncio
import os
import sys

# Add the parent directory to sys.path to import from app
sys.path.append(os.getcwd())

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionLocal
from app.db.models import User, CreatorProfile

async def audit_users():
    async with AsyncSessionLocal() as db:
        # Load users with their creator profiles
        result = await db.execute(
            select(User).options(selectinload(User.creator_profile))
        )
        users = result.scalars().all()
        
        print(f"Total users: {len(users)}")
        print("-" * 50)
        
        creators = [u for u in users if u.role == "creator"]
        print(f"Total Creators: {len(creators)}")
        
        for user in users:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Phone: {user.phone}")
            print(f"Full Name: {user.full_name}")
            print(f"Role: {user.role}")
            
            if user.creator_profile:
                cp = user.creator_profile
                print(f"  --- Creator Profile ---")
                print(f"  Display Name: {cp.display_name}")
                print(f"  Slug: {cp.slug}")
                print(f"  Niche: {cp.niche}")
                print(f"  Vertical: {cp.vertical}")
                print(f"  Status: {cp.verification_status}")
            
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(audit_users())
