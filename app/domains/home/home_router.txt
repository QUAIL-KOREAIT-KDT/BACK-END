# BACK-END/app/domains/home/router.py

from fastapi import APIRouter
from app.domains.home.service import WeatherService

router = APIRouter()
service = WeatherService()

@router.get("/molddate")
async def get_weather_risk(token):
    """메인 페이지 당일 곰팡이 지수 조회\n
    토큰에서 아이디를 뽑고 아이디로 주소를 뽑는다"""
    await service.get_mold_risk(token)
    return {
        "date": "20260124 1325",
        "temp": -220,
        "humid": 0,
        "mold_index": "매우 양호", 
        # "message": "대중이 드립처럼 싸해요."
    }

@router.get("/weather")
async def today_weather(token):
    """오늘 날씨만 뽑아옵니다."""
    await service.get_weahter_info(token)
    return {
        "date": "20260124 1318",
        "region": "서울",
        "temp": "-200",
        "humid": "100",
        "dew_point": "-118",
        "PP": "0",
        "mold_index": "34"
    }

@router.get("/refresh")
async def get_refresh_info(token):
    """환기 정보를 가져옵니다.
    1. 강수확률이 10퍼 이하인 데이터를 기준으로 3시간 연속인 정보를 뽑아온다
    2. 있으면 그 시간리스트를 준다.
    3. 없으면 오늘 환기는 곰팡이한테 주세요.
    """
    await service.get_refresh_info(token)
    return {
        "region": "서울",
        "date_list": ["20260124 1300", "20260124 1400", "20260124 1500"],
    }