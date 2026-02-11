# BACK-END/app/domains/home/schemas.py

from pydantic import BaseModel
from typing import List, Optional

class WeatherDetail(BaseModel):
    time: str          # "14:00" 형태
    temp: float        # 기온
    humid: float       # 습도
    rain_prob: int     # 강수확률
    condition: str     # 간단 상태 (예: "쾌적", "습함" 등)

class VentilationTime(BaseModel):
    date: str          # "2024-01-29"
    start_time: str    # "14:00"
    end_time: str      # "17:00"
    description: str   # "환기하기 딱 좋은 시간이에요!"

# [NEW] 단일 시점의 위험도 정보
class MoldRiskItem(BaseModel):
    time: str          # "13:00" (해당 예보 시간)
    score: float       # 0.0 ~ 100.0
    level: str         # "SAFE", "WARNING", "DANGER"
    type: str          # "MAX" (최대), "MIN" (최소), "CURRENT" (현재예보)
    message: str       # 사용자 안내 메시지 (간략)
    
    # 상세 정보 (디버깅 및 그래프용)
    temp_used: float   # 계산에 쓰인 실내 온도
    humid_used: float  # 계산에 쓰인 실내 습도

class HomeResponse(BaseModel):
    region_address: str
    
    # 현재 날씨 (상단 표시용)
    current_weather: List[WeatherDetail]
    
    # 환기 시간 추천
    ventilation_times: List[VentilationTime]
    
    # [변경된 요구사항] 곰팡이 위험도 리스트 (최대, 최소, 현재)
    risk_forecast: List[MoldRiskItem] = []