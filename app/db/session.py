from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency for getting database session."""
    print("DEBUG: Entering get_db...")
    async with AsyncSessionLocal() as session:
        try:
            print("DEBUG: Yielding database session...")
            yield session
            print("DEBUG: Committing session (in get_db)...")
            await session.commit()
            print("DEBUG: Session committed.")
        except Exception as e:
            print(f"DEBUG: Exception in get_db: {str(e)}")
            await session.rollback()
            raise
        finally:
            print("DEBUG: Closing session...")
            await session.close()
            print("DEBUG: Session closed.")
