"""
S3-Compatible Storage Client - Cloud-Agnostic

Works with:
- AWS S3
- Google Cloud Storage (via S3-compatible API)
- Azure Blob Storage (via S3-compatible API)
- MinIO (local development)
- DigitalOcean Spaces
- Backblaze B2

Usage:
    from app.services.storage import get_storage_client, StorageClient
    
    # Upload a file
    storage = get_storage_client()
    storage.upload_file("local.csv", "uploads/data.csv")
    
    # Download a file
    storage.download_file("uploads/data.csv", "local.csv")
    
    # Upload bytes
    storage.upload_bytes(b"hello world", "test.txt")
    
    # Generate presigned URL
    url = storage.get_presigned_url("uploads/data.csv", expires_in=3600)
"""

from __future__ import annotations

import io
from typing import Optional, BinaryIO, Union
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class StorageClient:
    """S3-compatible storage client."""
    
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        use_ssl: bool = False,
    ):
        """
        Initialize S3-compatible storage client.
        
        Args:
            endpoint_url: S3 endpoint (e.g., http://localhost:9000 for MinIO)
            access_key: Access key ID
            secret_key: Secret access key
            bucket: Default bucket name
            region: AWS region (default: us-east-1)
            use_ssl: Whether to use SSL
        """
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        
        # Configure boto3 client
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},  # Required for MinIO
            ),
            use_ssl=use_ssl,
        )
        
        self.resource = boto3.resource(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            use_ssl=use_ssl,
        )
        
        logger.info(
            "Storage client initialized",
            endpoint=endpoint_url,
            bucket=bucket,
        )
    
    def ensure_bucket_exists(self) -> bool:
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    logger.info("Created bucket", bucket=self.bucket)
                    return True
                except ClientError as create_error:
                    logger.error("Failed to create bucket", error=str(create_error))
                    return False
            logger.error("Bucket check failed", error=str(e))
            return False
    
    def upload_file(
        self,
        local_path: str | Path,
        remote_key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """
        Upload a local file to storage.
        
        Args:
            local_path: Path to local file
            remote_key: Remote object key (path in bucket)
            content_type: Optional MIME type
            
        Returns:
            True if successful
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            
            self.client.upload_file(
                str(local_path),
                self.bucket,
                remote_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info("Uploaded file", local=str(local_path), remote=remote_key)
            return True
        except Exception as e:
            logger.error("Upload failed", error=str(e), local=str(local_path))
            return False
    
    def download_file(self, remote_key: str, local_path: str | Path) -> bool:
        """
        Download a file from storage.
        
        Args:
            remote_key: Remote object key
            local_path: Path to save locally
            
        Returns:
            True if successful
        """
        try:
            # Ensure parent directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.client.download_file(self.bucket, remote_key, str(local_path))
            logger.info("Downloaded file", remote=remote_key, local=str(local_path))
            return True
        except Exception as e:
            logger.error("Download failed", error=str(e), remote=remote_key)
            return False
    
    def upload_bytes(
        self,
        data: bytes,
        remote_key: str,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """
        Upload bytes directly to storage.
        
        Args:
            data: Bytes to upload
            remote_key: Remote object key
            content_type: MIME type
            
        Returns:
            True if successful
        """
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=remote_key,
                Body=data,
                ContentType=content_type,
            )
            logger.info("Uploaded bytes", remote=remote_key, size=len(data))
            return True
        except Exception as e:
            logger.error("Upload bytes failed", error=str(e))
            return False
    
    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        remote_key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """
        Upload a file-like object to storage.
        
        Args:
            fileobj: File-like object (e.g., from file upload)
            remote_key: Remote object key
            content_type: Optional MIME type
            
        Returns:
            True if successful
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            
            self.client.upload_fileobj(
                fileobj,
                self.bucket,
                remote_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info("Uploaded fileobj", remote=remote_key)
            return True
        except Exception as e:
            logger.error("Upload fileobj failed", error=str(e))
            return False
    
    def download_bytes(self, remote_key: str) -> Optional[bytes]:
        """
        Download file as bytes.
        
        Args:
            remote_key: Remote object key
            
        Returns:
            File contents as bytes, or None if failed
        """
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=remote_key)
            return response["Body"].read()
        except Exception as e:
            logger.error("Download bytes failed", error=str(e), remote=remote_key)
            return None
    
    def get_presigned_url(
        self,
        remote_key: str,
        expires_in: int = 3600,
        http_method: str = "GET",
    ) -> Optional[str]:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            remote_key: Remote object key
            expires_in: URL expiration in seconds (default: 1 hour)
            http_method: HTTP method (GET for download, PUT for upload)
            
        Returns:
            Presigned URL, or None if failed
        """
        try:
            client_method = "get_object" if http_method == "GET" else "put_object"
            url = self.client.generate_presigned_url(
                ClientMethod=client_method,
                Params={"Bucket": self.bucket, "Key": remote_key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error("Presigned URL generation failed", error=str(e))
            return None
    
    def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict]:
        """
        List objects in bucket.
        
        Args:
            prefix: Filter by prefix (folder path)
            max_keys: Maximum number of results
            
        Returns:
            List of object metadata dicts
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            
            objects = []
            for obj in response.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                })
            
            return objects
        except Exception as e:
            logger.error("List objects failed", error=str(e))
            return []
    
    def delete_object(self, remote_key: str) -> bool:
        """
        Delete an object from storage.
        
        Args:
            remote_key: Remote object key
            
        Returns:
            True if successful
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=remote_key)
            logger.info("Deleted object", remote=remote_key)
            return True
        except Exception as e:
            logger.error("Delete failed", error=str(e), remote=remote_key)
            return False
    
    def object_exists(self, remote_key: str) -> bool:
        """
        Check if an object exists.
        
        Args:
            remote_key: Remote object key
            
        Returns:
            True if object exists
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=remote_key)
            return True
        except ClientError:
            return False


# Singleton instance
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """
    Get or create storage client singleton.
    
    Returns:
        StorageClient instance
    """
    global _storage_client
    
    if _storage_client is None:
        settings = get_settings()
        _storage_client = StorageClient(
            endpoint_url=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            bucket=settings.storage_bucket,
            region=settings.storage_region,
            use_ssl=settings.storage_use_ssl,
        )
    
    return _storage_client


def reset_storage_client():
    """Reset storage client (useful for testing)."""
    global _storage_client
    _storage_client = None
