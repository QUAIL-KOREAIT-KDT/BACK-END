# BACK-END/app/core/lifespan.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine, Base

# [중요] 테이블 생성을 위해 모든 모델을 미리 메모리에 로드해야 합니다.
from app.domains.user.models import User
from app.domains.home.models import Weather
from app.domains.diagnosis.models import Diagnosis
from app.domains.dictionary.models import Dictionary

# 전역 객체 저장소
ml_models = {}
vector_db = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # [Startup] 서버 시작 시 실행
    print("🚀 [System] 서버 시작: DB 테이블 생성 및 리소스 로드...")

    # 1. DB 테이블 자동 생성 (테이블이 없을 때만 생성됨)
    async with engine.begin() as conn:
        # create_all은 동기 함수이므로 run_sync로 실행
        await conn.run_sync(Base.metadata.create_all)
    print("✅ [Database] 테이블 체크 및 생성 완료")

    # 2. AI 모델 로드 (기존 코드 유지)
    print("🚀 [System] YOLO AI 모델 및 Vector DB 로드 중...")
    ml_models["yolo"] = "DUMMY_YOLO_OBJECT" 
    
    yield # 서버 실행 중 (여기서 멈춰있음)
    
    # [Shutdown] 서버 종료 시 실행
    print("🛑 [System] 리소스 해제")
    ml_models.clear()
    vector_db.clear()
    
    # DB 커넥션 종료
    await engine.dispose()