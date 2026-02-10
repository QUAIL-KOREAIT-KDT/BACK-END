# BACK-END/app/utils/storage.py

import boto3
import uuid
import json
import io
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

    def upload_to_folder(self, file_bytes: io.BytesIO, label: str, file_uuid: str,
                         folder_type: str = "dataset", content_type: str = "image/jpeg",
                         file_ext: str = "jpg") -> str:
        """
        라벨 기반 S3 폴더에 이미지 업로드

        Args:
            file_bytes: 업로드할 파일의 BytesIO
            label: "G0" ~ "G4"
            file_uuid: 파일 고유 UUID
            folder_type: "dataset" (원본) 또는 "gradcam" (CAM 이미지)
            content_type: MIME type
            file_ext: 파일 확장자

        Returns:
            S3 URL
        """
        if folder_type == "gradcam":
            s3_key = f"gradcam/{label}/{file_uuid}_cam.{file_ext}"
        else:
            s3_key = f"dataset/{label}/{file_uuid}.{file_ext}"

        self.s3_client.upload_fileobj(
            file_bytes,
            self.bucket_name,
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )

        return f"https://{self.bucket_name}.s3.{settings.AWS_REGION_NAME}.amazonaws.com/{s3_key}"

    def upload_json(self, json_data: dict, label: str, file_uuid: str) -> str:
        """
        JSON sidecar 파일을 S3에 업로드 (바운딩박스 좌표 등)

        Args:
            json_data: 저장할 JSON 딕셔너리
            label: "G0" ~ "G4"
            file_uuid: 파일 고유 UUID

        Returns:
            S3 URL
        """
        s3_key = f"dataset/{label}/{file_uuid}.json"

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=json.dumps(json_data, ensure_ascii=False),
            ContentType='application/json'
        )

        return f"https://{self.bucket_name}.s3.{settings.AWS_REGION_NAME}.amazonaws.com/{s3_key}"
