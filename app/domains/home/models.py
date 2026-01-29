# BACK-END/app/domains/home/models.py

from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from app.core.database import Base

class Weather(Base):
    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)

    # [수정] 지역 이름(region) 삭제 -> 격자 좌표(nx, ny) 추가
    nx = Column(Integer, nullable=False) 
    ny = Column(Integer, nullable=False)
    
    # [수정] 컬럼명 통일 (pp -> rain_prob)
    temp = Column(Float, nullable=False)         # 기온 (TMP)
    humid = Column(Float, nullable=False)        # 습도 (REH)
    rain_prob = Column(Integer, nullable=False)  # 강수확률 (POP)
    
    # 파생 데이터
    dew_point = Column(Float, nullable=True)     # 이슬점

    # [중요] 날짜 + 좌표가 같으면 중복 저장 금지
    __table_args__ = (
        UniqueConstraint('date', 'nx', 'ny', name='uix_weather_grid_date'),
    )