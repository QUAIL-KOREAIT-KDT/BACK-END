# BACK-END/app/core/lifespan.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.database import engine, Base

# [중요] 테이블 생성을 위해 모든 모델을 미리 메모리에 로드해야 합니다.
from app.domains.user.models import User
from app.domains.home.models import Weather
from app.domains.diagnosis.models import Diagnosis
from app.domains.dictionary.models import Dictionary
from app.domains.notification.models import Notification  # 알림 테이블
from app.domains.fortune.models import FortuneHistory     # 운세 이력 테이블

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.scheduler import fetch_daily_weather_job, calculate_daily_risk_job, send_morning_notification_job, initialize_weather_data

# 전역 객체 저장소
ml_models = {}
vector_db = {}
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # [Startup] 서버 시작 시 실행
    print("🚀 [System] 서버 시작: DB 테이블 생성 및 리소스 로드...")

    # 1. DB 테이블 자동 생성 (테이블이 없을 때만 생성됨)
    async with engine.begin() as conn:
        # create_all은 동기 함수이므로 run_sync로 실행
        await conn.run_sync(Base.metadata.create_all)
    print("✅ [Database] 테이블 체크 및 생성 완료")

    # 2. AI 모델 로드 (ONNX Runtime)
    print("🚀 [System] EfficientNet-B0 (ONNX) 모델 및 Vector DB 로드 중...")
    from app.domains.diagnosis.ai_engine import EfficientNetEngine
    import os
    _weights_path = os.path.join(os.path.dirname(__file__), "..", "domains", "diagnosis", "models", "efficientnet_b0_mold.onnx")
    _weights_path = os.path.abspath(_weights_path)
    print(f"📂 [Model] 가중치 경로: {_weights_path} (존재: {os.path.exists(_weights_path)})")
    ml_models["efficientnet"] = EfficientNetEngine(weights_path=_weights_path)
    

    # [시작 시 실행]
    print("🚀 서버 시작: 스케줄러를 가동합니다.")
    
    # 1. 00:00 날씨 수집 (11:12분으로 임의 수정)
    scheduler.add_job(fetch_daily_weather_job, 'cron', hour=0, minute=0)
    
    # 2. 01:00 위험도 계산
    scheduler.add_job(calculate_daily_risk_job, 'cron', hour=1, minute=0)
    
    # 3. 08:00 알림 발송
    scheduler.add_job(send_morning_notification_job, 'cron', hour=8, minute=0)
    
    scheduler.start()
    # await를 사용하여 이 작업이 끝날 때까지 서버가 대기하도록 함 (데이터 확보 우선)
    await initialize_weather_data()

    yield # 서버 실행 중 (여기서 멈춰있음)
    
    # [Shutdown] 서버 종료 시 실행
    # [종료 시 실행]
    print("🛑 서버 종료: 스케줄러를 정지합니다.")
    scheduler.shutdown()
    ml_models.clear()
    vector_db.clear()
    
    # DB 커넥션 종료
    await engine.dispose()