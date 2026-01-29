# BACK-END/app/domains/users/models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, BOOLEAN
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    # 사용자 고유번호
    id = Column(Integer, primary_key=True, index=True)

    # 카카오 아이디
    kakao_id = Column(String(50), unique=True, nullable=False)

    # 닉네임
    nickname = Column(String(50), nullable=True)

    # 창문 방향
    window_direction = Column(Enum("S", "N", "O", name="user_window_direction_types"), nullable=True)

    # 지하
    underground = Column(Enum("underground", "semi-basement", "others", name="underground_types"), nullable=True)

    # 주소
    address = Column(String(255), nullable=True)

    # ========== [추가할 부분] 기상청 좌표 연동용 ==========
    region_address = Column(String(255), nullable=True) # 예: "경기 안산시 상록구"
    grid_nx = Column(Integer, nullable=True)            # 기상청 X값
    grid_ny = Column(Integer, nullable=True)            # 기상청 Y값
    latitude = Column(Float, nullable=True)             # 위도
    longitude = Column(Float, nullable=True)            # 경도
    # ====================================================

    # 사용자 실내 온도
    indoor_temp = Column(Float, nullable=True)

    # 사용자 실내 습도
    indoor_humidity = Column(Float, nullable=True)

    # 알림 설정
    notification_settings = Column(Boolean, nullable=True)

    # 가입일
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    