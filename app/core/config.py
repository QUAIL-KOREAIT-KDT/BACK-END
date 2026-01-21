# BACK-END/app/core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "QUAIL (팡팡팡)"
    
    # [Source 9] 데이터베이스 연결
    # 현재 DB 없음(20260121 1000)
    # DATABASE_URL: str = "mysql+aiomysql://user:password@localhost/quail_db"
    
    # [Source 6] 기상청 API 키
    KMA_API_KEY: str = "5xfS3rylStCX0t68pSrQWQ"

    # 단기예보 공공데이터 포털 API키
    DATA_API_KEY: str = "7f07ccbfbacccbeaf93c52b4693b8fdd5c2c865056809869300a95af1e00a39c"
    
    # [Source 2, 5] AWS S3 및 OpenAI(RAG) 설정
    # 현재 AWS 및 RAG 없음(20260121 1000)
    # AWS_ACCESS_KEY_ID: str = "your_aws_key"
    # AWS_SECRET_ACCESS_KEY: str = "your_aws_secret"
    # AWS_BUCKET_NAME: str = "quail-bucket"
    # OPENAI_API_KEY: str = "your_openai_key"

    class Config:
        env_file = ".env"

settings = Settings()