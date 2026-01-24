# BACK-END/app/core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 1. 프로젝트 이름 (기본값 유지)
    PROJECT_NAME: str = "QUAIL (팡팡팡)"
    
    # 2. 데이터베이스 연결 (하드코딩 삭제 -> .env에서 필수 로드)
    DATABASE_URL: str 
    
    # 3. API 키 설정 (하드코딩 삭제 -> .env에서 필수 로드)
    # (만약 .env에 없으면 에러가 나도록 하여 실수를 방지합니다)
    KMA_API_KEY: str 
    DATA_API_KEY: str
    
    # 4. 선택적 설정 (기본값 None 허용)
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_BUCKET_NAME: str | None = None
    OPENAI_API_KEY: str | None = None

    class Config:
        # .env 파일을 읽어서 위 변수들에 자동으로 값을 채워줍니다.
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()