import asyncio
from app.db.session import engine, Base
from app.db.models import * # Ensure all models are loaded

async def sync_db():
    print("Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created successfully.")

if __name__ == "__main__":
    asyncio.run(sync_db())
