# BACK-END/app/core/lifespan.py

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import Base, engine

# Import models so SQLAlchemy metadata is populated before create_all().
from app.domains.diagnosis.models import Diagnosis
from app.domains.dictionary.models import Dictionary
from app.domains.fortune.models import FortuneHistory
from app.domains.home.models import Weather
from app.domains.notification.models import Notification
from app.domains.user.models import User

from app.core.scheduler import (
    calculate_daily_risk_job,
    fetch_daily_weather_job,
    initialize_weather_data,
    scheduler,
    send_morning_notification_job,
)

ml_models = {}
vector_db = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[System] Starting server: checking DB tables and loading resources...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] Table check complete")

    print("[System] Loading EfficientNet-B0 ONNX model and vector DB...")
    from app.domains.diagnosis.ai_engine import EfficientNetEngine

    weights_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "domains",
        "diagnosis",
        "models",
        "efficientnet_b0_mold.onnx",
    )
    weights_path = os.path.abspath(weights_path)
    print(f"[Model] weights_path={weights_path} exists={os.path.exists(weights_path)}")
    ml_models["efficientnet"] = EfficientNetEngine(weights_path=weights_path)

    if settings.ENABLE_SCHEDULER:
        print("[Scheduler] Starting scheduled jobs")

        scheduler.add_job(fetch_daily_weather_job, "cron", hour=0, minute=0)
        scheduler.add_job(calculate_daily_risk_job, "cron", hour=1, minute=0)
        scheduler.add_job(send_morning_notification_job, "cron", hour=8, minute=0)

        scheduler.start()

        if settings.FETCH_WEATHER_ON_STARTUP:
            asyncio.create_task(initialize_weather_data())
    else:
        print("[Scheduler] Disabled by settings")

    yield

    print("[System] Shutting down scheduler and resources")
    if scheduler.running:
        scheduler.shutdown()
    ml_models.clear()
    vector_db.clear()

    await engine.dispose()
