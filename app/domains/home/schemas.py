# BACK-END/app/domains/home/schemas.py

from pydantic import BaseModel
from typing import List
from datetime import datetime

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

class HomeResponse(BaseModel):
    region_address: str
    current_weather: List[WeatherDetail]       # 1. 오늘 현재시간 이후 예보
    ventilation_times: List[VentilationTime]   # 2. 환기 추천 시간대