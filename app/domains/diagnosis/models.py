# BACK-END/app/domains/diagnosis/models.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func  # [중요] DB의 함수(NOW)를 쓰기 위해 필요
from app.core.database import Base

class Diagnosis(Base):
    __tablename__ = "diagnosis"  # 실제 DB에 생성될 테이블 이름

    # 진단 작성글 번호
    # Integer이면서 primary_key=True이면 자동으로 1, 2, 3... 증가합니다.
    id = Column(Integer, primary_key=True, index=True)

    # 작성자 번호
    user_id = Column(Integer, nullable=False) # FK 설정은 나중에 관계 정의로 추가 가능
    
    # 진단 클래스
    result = Column(String(50), nullable=False)

    # 진단 신뢰도(확률)
    confidence = Column(Float, nullable=False)

    # 사용자 사진 경로
    image_path = Column(String(255), nullable=False)
    
    # 창문 방향 => 동,서,남,북, 기타(모름)
    window_direction = Column(Enum("E", "W", "S", "N", "O", name="diagnosis_window_direction_types"))

    # 곰팡이 위치 => 창문, 벽지, 부엌, 욕실, 천장, 음식
    mold_location = Column(Enum("Windows", "wallpaper", "kitchen", "bathroom", "ceiling", "food", name='mold_location_types'))

    # 2. 가입일 [datetime NOW()] 해결
    # server_default=func.now() : 데이터가 들어갈 때 DB가 알아서 시간을 찍어줌
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)