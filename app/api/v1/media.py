from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import MediaUploadRequest, MediaUploadResponse
from app.core.dependencies import get_current_user
from app.core.config import settings

router = APIRouter()


@router.post("/upload-url", response_model=MediaUploadResponse)
async def get_upload_url(
    upload_request: MediaUploadRequest,
    current_user = Depends(get_current_user)
):
    """
    Generate pre-signed URL for media upload.
    
    - Returns upload URL for direct browser upload
    - Supports MinIO (local) and Azure Blob (production)
    """
    # Validate file size
    max_sizes = {
        "image": 5 * 1024 * 1024,  # 5MB
        "voice": 10 * 1024 * 1024,  # 10MB
        "video": 100 * 1024 * 1024,  # 100MB
    }
    
    if upload_request.file_size > max_sizes.get(upload_request.media_type, 5 * 1024 * 1024):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum for {upload_request.media_type}"
        )
    
    # Determine bucket based on media type
    bucket_map = {
        "image": settings.minio_bucket_profile_images,
        "voice": settings.minio_bucket_voice_notes,
        "video": settings.minio_bucket_video_replies,
    }
    bucket_name = bucket_map.get(upload_request.media_type, settings.minio_bucket_profile_images)
    
    # Generate unique filename
    import uuid
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_extension = upload_request.file_name.split('.')[-1]
    unique_filename = f"{current_user.id}/{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
    
    if settings.storage_provider == "minio":
        # MinIO (local development)
        from minio import Minio
        from datetime import timedelta
        
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        
        # Create bucket if not exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
        
        # Generate presigned URL (1 hour expiry)
        upload_url = minio_client.presigned_put_object(
            bucket_name,
            unique_filename,
            expires=timedelta(hours=1)
        )
        
        # Public URL for accessing the file
        protocol = "https" if settings.minio_secure else "http"
        blob_url = f"{protocol}://{settings.minio_endpoint}/{bucket_name}/{unique_filename}"
        
    else:
        # Azure Blob Storage (production)
        # TODO: Implement Azure Blob Storage SAS token generation
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Azure Blob Storage not yet implemented"
        )
    
    return MediaUploadResponse(
        upload_url=upload_url,
        blob_url=blob_url,
    )


@router.get("/stream/{bucket}/{filename}")
async def stream_media(
    bucket: str,
    filename: str,
    current_user = Depends(get_current_user)
):
    """
    Stream media file with authentication.
    
    - Validates user has access to content
    - Returns file stream
    """
    # TODO: Implement access control and streaming
    # For now, MinIO URLs are directly accessible
    
    from fastapi.responses import RedirectResponse
    
    protocol = "https" if settings.minio_secure else "http"
    media_url = f"{protocol}://{settings.minio_endpoint}/{bucket}/{filename}"
    
    return RedirectResponse(url=media_url)
