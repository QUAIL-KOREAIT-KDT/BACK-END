# BACK-END/app/domains/weather/service.py

from app.domains.weather.utils import convert_gps_to_grid

class WeatherService:
    async def get_mold_risk(self, address: str):
        # 1. 주소 -> 위경도 변환 -> 격자 변환 [Source 10]
        # 2. 기상청 API 호출 [Source 6]
        # 3. 곰팡이 지수(안전~위험) 계산 [Source 3, 6]
        # 4. 알림 필요 여부 체크 [Source 8]
        pass