"""S3 operations for AC Server Manager."""

import logging
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Manager:
    """Manages S3 operations for AC server pack files."""
    
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        """Initialize S3 manager.
        
        Args:
            bucket_name: Name of the S3 bucket
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = boto3.client("s3", region_name=region)
        
    def create_bucket(self) -> bool:
        """Create S3 bucket if it doesn't exist.
        
        Returns:
            True if bucket was created or already exists, False otherwise
        """
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} already exists")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # Bucket doesn't exist, create it
                try:
                    if self.region == "us-east-1":
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region}
                        )
                    logger.info(f"Created bucket {self.bucket_name}")
                    return True
                except ClientError as create_error:
                    logger.error(f"Error creating bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False
                
    def upload_pack(self, local_path: Path, s3_key: Optional[str] = None) -> Optional[str]:
        """Upload AC server pack to S3.
        
        Args:
            local_path: Path to the local pack file
            s3_key: S3 object key (defaults to filename)
            
        Returns:
            S3 key of uploaded file, or None if upload failed
        """
        if not local_path.exists():
            logger.error(f"Pack file not found: {local_path}")
            return None
            
        if s3_key is None:
            s3_key = f"packs/{local_path.name}"
            
        try:
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key
            )
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_key}")
            return s3_key
        except ClientError as e:
            logger.error(f"Error uploading pack: {e}")
            return None
            
    def download_pack(self, s3_key: str, local_path: Path) -> bool:
        """Download AC server pack from S3.
        
        Args:
            s3_key: S3 object key
            local_path: Local path to save the file
            
        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Create parent directory if it doesn't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                str(local_path)
            )
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Error downloading pack: {e}")
            return False
            
    def list_packs(self) -> list[str]:
        """List all pack files in the S3 bucket.
        
        Returns:
            List of S3 keys for pack files
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="packs/"
            )
            
            if "Contents" not in response:
                return []
                
            return [obj["Key"] for obj in response["Contents"]]
        except ClientError as e:
            logger.error(f"Error listing packs: {e}")
            return []
            
    def delete_pack(self, s3_key: str) -> bool:
        """Delete a pack file from S3.
        
        Args:
            s3_key: S3 object key to delete
            
        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting pack: {e}")
            return False
