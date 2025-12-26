from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import engine
from app.db.models import Base
from app.api.v1 import auth, creators, clubs, subscriptions, messages, media


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting OnlyForU API...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database tables created")
    print(f"Environment: {settings.environment}")
    print(f"Storage: {settings.storage_provider}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down OnlyForU API...")
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="OnlyForU API",
    description="Async communication platform for regional Indian creators and fans",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Request logging middleware (for debugging)
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"🔵 Incoming request: {request.method} {request.url.path} from {request.headers.get('origin', 'NO ORIGIN')}")
    response = await call_next(request)
    print(f"🟢 Response status: {response.status_code}")
    return response

# CORS middleware - use origins from settings (environment variable)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),  # Read from CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "storage": settings.storage_provider,
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(creators.router, prefix="/api/v1/creators", tags=["Creators"])
app.include_router(clubs.router, prefix="/api/v1/clubs", tags=["Fan Clubs"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])
app.include_router(messages.router, prefix="/api/v1/messages", tags=["Messages"])
from app.api.v1 import feed
app.include_router(feed.router, prefix="/api/v1/feed", tags=["Feed"])
app.include_router(media.router, prefix="/api/v1/media", tags=["Media"])
from app.api.v1 import websockets
app.include_router(websockets.router, prefix="/api/v1/ws", tags=["WebSockets"])
from app.api.v1 import creator_services
app.include_router(creator_services.router, prefix="/api/v1/creator", tags=["Creator Services"])
from app.api.v1 import analytics
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
from app.api.v1 import bookings
app.include_router(bookings.router, prefix="/api/v1", tags=["Bookings"])
from app.api.v1 import follow_ups
app.include_router(follow_ups.router, prefix="/api/v1", tags=["Follow-ups"])
from app.api.v1 import payments
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    if settings.is_development:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
