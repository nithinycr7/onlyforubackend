"""
Azure Blob Storage Service
Handles video upload/download for consultation questions and responses
"""

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import os
from typing import Optional
import uuid


class AzureStorageService:
    """Service for managing video uploads to Azure Blob Storage."""
    
    def __init__(self):
        # Get Azure credentials from environment
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER", "usersdemo")
        
        if not self.connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable is required")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self._ensure_container_exists()
    
    def _ensure_container_exists(self):
        """Ensure the container exists, create if it doesn't."""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
        except Exception as e:
            print(f"Error ensuring container exists: {e}")
    
    async def upload_question_video(
        self, 
        file_data: bytes, 
        booking_id: str,
        file_extension: str = "mp4"
    ) -> str:
        """
        Upload question video to Azure Blob Storage.
        
        Args:
            file_data: Video file bytes
            booking_id: Booking ID for naming
            file_extension: File extension (default: mp4)
        
        Returns:
            Blob URL
        """
        from azure.storage.blob import ContentSettings
        
        timestamp = int(datetime.utcnow().timestamp())
        blob_name = f"questions/{booking_id}_{timestamp}.{file_extension}"
        
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        # Upload with content type
        blob_client.upload_blob(
            file_data, 
            overwrite=True,
            content_settings=ContentSettings(content_type=f'video/{file_extension}')
        )
        
        return blob_client.url
    
    async def upload_question_audio(
        self, 
        file_data: bytes, 
        booking_id: str,
        file_extension: str = "mp3"
    ) -> str:
        """
        Upload question audio to Azure Blob Storage.
        
        Args:
            file_data: Audio file bytes
            booking_id: Booking ID for naming
            file_extension: File extension (default: mp3)
        
        Returns:
            Blob URL
        """
        from azure.storage.blob import ContentSettings
        
        timestamp = int(datetime.utcnow().timestamp())
        blob_name = f"questions/audio_{booking_id}_{timestamp}.{file_extension}"
        
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        # Upload with content type
        blob_client.upload_blob(
            file_data, 
            overwrite=True,
            content_settings=ContentSettings(content_type=f'audio/{file_extension}')
        )
        
        return blob_client.url
    
    async def upload_response_media(
        self, 
        file_data: bytes, 
        booking_id: str,
        media_type: str = "voice",  # 'voice' or 'video'
        file_extension: str = "mp4"
    ) -> str:
        """
        Upload creator response media to Azure Blob Storage.
        
        Args:
            file_data: Media file bytes
            booking_id: Booking ID for naming
            media_type: 'voice' or 'video'
            file_extension: File extension
        
        Returns:
            Blob URL
        """
        from azure.storage.blob import ContentSettings
        
        timestamp = int(datetime.utcnow().timestamp())
        blob_name = f"responses/{booking_id}_{timestamp}.{file_extension}"
        
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        # Set appropriate content type
        content_type = f"video/{file_extension}" if media_type == "video" else f"audio/{file_extension}"
        
        blob_client.upload_blob(
            file_data, 
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )
        
        return blob_client.url
    
    async def upload_response_audio(
        self, 
        file_data: bytes, 
        booking_id: str,
        file_extension: str = "mp3"
    ) -> str:
        """Upload creator audio response."""
        return await self.upload_response_media(
            file_data=file_data,
            booking_id=booking_id,
            media_type="voice",
            file_extension=file_extension
        )
    
    async def upload_response_video(
        self, 
        file_data: bytes, 
        booking_id: str,
        file_extension: str = "mp4"
    ) -> str:
        """Upload creator video response."""
        return await self.upload_response_media(
            file_data=file_data,
            booking_id=booking_id,
            media_type="video",
            file_extension=file_extension
        )
    
    def get_signed_url(self, blob_url: str, expiry_hours: int = 24) -> str:
        """
        Generate a signed URL for secure video playback.
        
        Args:
            blob_url: Full blob URL
            expiry_hours: URL expiry time in hours
        
        Returns:
            Signed URL with SAS token
        """
        try:
            # If URL already has SAS parameters, return as-is
            if '?se=' in blob_url or '&se=' in blob_url:
                return blob_url
            
            # Extract blob name from URL
            blob_name = blob_url.split(f"{self.container_name}/")[1]
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            return f"{blob_url}?{sas_token}"
        except Exception as e:
            print(f"Error generating signed URL: {e}")
            return blob_url  # Return original URL if SAS generation fails
    
    async def upload_profile_image(
        self, 
        file_data: bytes, 
        user_id: str,
        file_extension: str = "jpg"
    ) -> str:
        """
        Upload profile image to Azure Blob Storage.
        
        Args:
            file_data: Image file bytes
            user_id: User/Creator ID for naming
            file_extension: File extension
        
        Returns:
            Blob URL
        """
        from azure.storage.blob import ContentSettings
        
        blob_name = f"profiles/{user_id}.{file_extension}"
        
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        # Upload with content type
        blob_client.upload_blob(
            file_data, 
            overwrite=True,
            content_settings=ContentSettings(content_type=f'image/{file_extension}')
        )
        
        return blob_client.url

    async def delete_blob(self, blob_url: str) -> bool:
        """
        Delete a blob from storage.
        
        Args:
            blob_url: Full blob URL
        
        Returns:
            True if deleted successfully
        """
        try:
            blob_name = blob_url.split(f"{self.container_name}/")[1]
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            blob_client.delete_blob()
            return True
        except Exception as e:
            print(f"Error deleting blob: {e}")
            return False


# Singleton instance
azure_storage = AzureStorageService()
