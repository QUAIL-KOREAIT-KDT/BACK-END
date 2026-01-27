# BACK-END/app/domains/users/models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"  # 여기에 적힌 이름으로 DB에 생성됨

    # 사용자 고유번호
    id = Column(Integer, primary_key=True, index=True)

    # 카카오 아이디
    kakao_id = Column(String(50), unique=True, nullable=False)

    # 닉네임
    nickname = Column(String(50), nullable=True)

    # 창문 방향
    window_direction = Column(Enum("E", "W", "S", "N", "O", name="user_window_direction_types"), nullable=True)

    # 지하
    underground = Column(Enum("underground", "semi-basement", name="underground_types"), nullable=True)

    # 주소
    address = Column(String(255), nullable=True)

    # 날씨 연결할 근처 가까운 주소
    output_address = Column(String(50), nullable=True)

    # 사용자 실내 온도
    indoor_temp = Column(Float, nullable=True)

    # 사용자 실내 습도
    indoor_humidity = Column(Float, nullable=True)

    # 가입일
    created_at = Column(DateTime(timezone=True), server_default=func.now())