# BACK-END/app/utils/storage.py

import boto3
import uuid
from fastapi import UploadFile
from app.core.config import settings

class StorageClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME
        )
        self.bucket_name = settings.AWS_BUCKET_NAME

    async def upload_image(self, file: UploadFile) -> str:
        """
        이미지를 S3에 업로드하고 public URL을 반환합니다.
        파일명 중복 방지를 위해 UUID를 사용합니다.
        """
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # S3 업로드 (동기 함수이므로 필요 시 run_in_executor 등으로 감쌀 수 있음)
        # file.file을 직접 넘겨 스트림 업로드
        self.s3_client.upload_fileobj(
            file.file,
            self.bucket_name,
            unique_filename,
            ExtraArgs={'ContentType': file.content_type}
        )

        # 업로드된 이미지의 URL 생성 (ap-northeast-2 기준)
        image_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION_NAME}.amazonaws.com/{unique_filename}"
        
        return image_url