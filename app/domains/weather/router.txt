# BACK-END/app/domains/weather/router.py

from fastapi import APIRouter
from app.domains.weather.schemas import ImageData
from app.domains.weather.service import WeatherService

router = APIRouter()
service = WeatherService()

@router.get("/current")
async def get_weather_risk(address: str):
    """[Source 3] 메인페이지: 날씨 정보 및 곰팡이 지수 출력"""
    await service.get_mold_risk(address)
    # [Source 6] 4단계 위험도 반환 예시
    return {
        "temp": 24.5,
        "humidity": 72,
        "risk_level": "주의", 
        "alert_message": "습도가 높습니다. 환기가 필요합니다."
    }

@router.post("/img-upload")
async def upload_image(imgdata:ImageData):
    """[Source 6] 이미지 업로드 및 처리"""
    await service.process_image(imgdata)
    # 이미지 업로드 및 처리 로직 구현
    return {"status": "success"}