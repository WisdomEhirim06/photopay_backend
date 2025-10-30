import os
import uuid
import mimetypes
from typing import Dict
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()


class GCSService:
    """
    Handles image uploads and retrievals using Google Cloud Storage.
    """

    def __init__(self):
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")

        if not credentials_path or not os.path.exists(credentials_path):
            raise Exception("Google Cloud credentials not found. Check GOOGLE_APPLICATION_CREDENTIALS path.")

        if not self.bucket_name:
            raise Exception("Missing GCS_BUCKET_NAME in environment.")

        # Initialize client and bucket
        self.client = storage.Client.from_service_account_json(credentials_path)
        self.bucket = self.client.bucket(self.bucket_name)

    async def upload_file(self, file_content: bytes, filename: str) -> Dict[str, str]:
        """
        Upload a file to Google Cloud Storage and return its public URL.
        """
        try:
            ext = os.path.splitext(filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"

            blob = self.bucket.blob(unique_filename)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            blob.upload_from_string(file_content, content_type=content_type)
            
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{unique_filename}"

            print(f"✅ Uploaded to GCS: {public_url}")

            return {
                "file_id": unique_filename,
                "file_url": public_url,
                "public_url": public_url
            }

        except Exception as e:
            raise Exception(f"GCS upload failed: {e}")

    async def get_file_info(self, file_id: str) -> Dict[str, str]:
        """
        Get file info from Google Cloud Storage (metadata and URL).
        """
        try:
            blob = self.bucket.get_blob(file_id)
            if not blob:
                raise Exception("File not found in GCS")

            return {
                "file_id": file_id,
                "file_url": blob.public_url,
                "size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated.isoformat() if blob.updated else None
            }
        except Exception as e:
            raise Exception(f"Failed to retrieve file info: {e}")

    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from Google Cloud Storage (used instead of 'unpin').
        """
        try:
            blob = self.bucket.blob(file_id)
            blob.delete()
            print(f"🗑️ Deleted file from GCS: {file_id}")
            return True
        except Exception as e:
            print(f"⚠️ Failed to delete file: {e}")
            return False


# Singleton instance
gcs_service = GCSService()
