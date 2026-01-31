# BACK-END/app/domains/home/schemas.py

from pydantic import BaseModel
from typing import List
from datetime import datetime
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
    description: str   # "환기하기 딱 좋은 시간이에요! (평균 습도 35%)"

# [NEW] 위험도 정보 스키마 추가
class RiskInfo(BaseModel):
    score: float
    level: str
    message: str
    details: Optional[dict] = None  # 벽 온도 등 상세 정보 (디버깅/표시용)

class HomeResponse(BaseModel):
    region_address: str
    current_weather: List[WeatherDetail]
    ventilation_times: List[VentilationTime]
    risk_info: Optional[RiskInfo] = None # 추가