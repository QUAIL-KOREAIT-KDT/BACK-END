# BACK-END/app/domains/home/client.py

import requests
import json
from datetime import datetime
from urllib.parse import unquote # [추가] 키 디코딩용
from app.core.config import settings

class WeatherClient:
    def __init__(self):
        # .env에서 가져온 키가 인코딩된 상태라면 디코딩해서 사용해야 requests에서 안전함
        self.api_key = unquote(settings.DATA_API_KEY)
        self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

    async def fetch_forecast(self, nx: int, ny: int):
        # 1. Base Time 계산 (단기예보는 02, 05, 08... 3시간 단위)
        now = datetime.now()
        base_date = now.strftime("%Y%m%d")
        
        current_hour = now.hour
        # API 제공 시간이 조금 늦을 수 있으므로(예: 02:10 발표), 안전하게 이전 타임 사용
        if current_hour < 2:
            # 0~1시는 전날 23시 데이터를 봐야 함 (로직 복잡도 줄이기 위해 전날 로직 생략하고 02시로 가정하거나 예외처리)
            # 여기서는 편의상 전날 23시 데이터가 아닌, 당일 가장 빠른 02시를 기다리거나 빈 리스트 반환
            return [] 
        
        # (시간 - 2) // 3 * 3 + 2 공식을 쓰면 02, 05, 08... 이 나옴
        base_h = ((current_hour - 2) // 3) * 3 + 2
        base_time = f"{base_h:02d}00"

        params = {
            'serviceKey': self.api_key,
            'pageNo': '1',
            'numOfRows': '1000', # 넉넉하게 요청
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': str(nx),
            'ny': str(ny)
        }

        print(f"📡 기상청 API 요청: {base_date} {base_time} (nx={nx}, ny={ny})")
        
        try:
            # requests는 동기 라이브러리지만, 간단한 구현을 위해 여기서 사용
            # (추후 성능 이슈 시 aiohttp로 교체 권장)
            response = requests.get(self.base_url, params=params, timeout=10)
            
            # JSON 파싱
            if response.status_code != 200:
                print(f"❌ API 상태 코드 에러: {response.status_code}")
                return []

            data = response.json()
            
            # 응답 구조 확인
            response_header = data.get('response', {}).get('header', {})
            if response_header.get('resultCode') != '00':
                print(f"❌ API 결과 에러: {response_header.get('resultMsg')}")
                return []

            items = data['response']['body']['items']['item']
            return items
            
        except Exception as e:
            print(f"❌ API 호출 중 예외 발생: {e}")
            return []