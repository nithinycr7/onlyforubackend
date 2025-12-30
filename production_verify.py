import asyncio
import os
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.db.models import ServiceTemplate

os.environ["DATABASE_URL"] = "postgresql+asyncpg://onlyforu_user:aXeF5PGF6UlRMNgkFKT1CtEILdSkkbU0@dpg-d579uvbuibrs73a1td10-a.singapore-postgres.render.com/onlyforu_db"

async def verify():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(ServiceTemplate.id)))
        count = result.scalar()
        print(f"Found {count} service templates in production.")

if __name__ == "__main__":
    asyncio.run(verify())
