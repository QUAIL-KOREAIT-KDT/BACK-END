# BACK-END/app/utils/storage.py

from fastapi import UploadFile

class StorageClient:
    async def upload_image(self, file: UploadFile) -> str:
        """[Source 2, 5] AWS S3 이미지 업로드 및 URL 반환"""
        pass