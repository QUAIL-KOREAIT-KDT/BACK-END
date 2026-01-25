# BACK-END/app/domains/dictionary/models.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text
from sqlalchemy.sql import func  # [중요] DB의 함수(NOW)를 쓰기 위해 필요
from app.core.database import Base

class Dictionary(Base):
    __tablename__ = "dictionary"

    # 아이디
    id = Column(Integer, primary_key=True, index=True)
    
    # 클래스 G1~G8 
    label = Column(String(50), nullable=False)

    # 곰팡이 이름 Stachybotrys, Alternaria ...
    name = Column(String(50), nullable=False)

    # 1.색상, 2.외형, 3.환경, 4.유해정보를 합쳐서 저장 \t로 구분
    feature = Column(Text, nullable=False)

    # 곰팡이 출몰 위치
    location = Column(String(255), nullable=False)
    
    # 썸네일 경로
    image_path = Column(String(255), nullable=False)

    # 디테일 이미지 경로
    detail_image_path = Column(String(255), nullable=False)

    # 처리방법 => 생성위치에 따른 해결 방법(**\t**으로 구분하여 출력)
    solution = Column(Text, nullable=False)

    # 예방법
    preventive = Column(Text, nullable=False)

    # 키워드
    keyword = Column(Text)

    # 벡터 아이디
    vector_id = Column(String(512))
