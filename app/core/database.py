# BACK-END/app/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# 1. 비동기 엔진 생성 (echo=True는 쿼리 로그를 출력해줍니다)
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# 2. 비동기 세션 팩토리 (DB 요청 시마다 세션을 찍어내는 틀)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. 모델들이 상속받을 Base 클래스
Base = declarative_base()

# API에서 DB를 사용할 수 있게 해주는 함수
async def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()