# BACK-END/app/domains/home/client.py

import asyncio
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import unquote # [추가] 키 디코딩용
from app.core.config import settings

class WeatherClient:
    def __init__(self):
        # .env에서 가져온 키가 인코딩된 상태라면 디코딩해서 사용해야 requests에서 안전함
        self.api_key = unquote(settings.DATA_API_KEY)
        self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

    async def fetch_forecast(self, nx: int, ny: int):
        now = datetime.now()
        
        # [수정] Base Time 계산 로직 강화
        if now.hour < 2:
            # 0시~2시 사이면 '어제 23시' 데이터를 요청
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
            base_time = "2300"
        else:
            base_date = now.strftime("%Y%m%d")
            # (현재시간 - 2) // 3 * 3 + 2 공식 (02, 05, 08...)
            base_h = ((now.hour - 2) // 3) * 3 + 2
            base_time = f"{base_h:02d}00"

        params = {
            'serviceKey': self.api_key,
            'pageNo': '1',
            'numOfRows': '1000', 
            'dataType': 'JSON',
            'base_date': base_date,
            'base_time': base_time,
            'nx': str(nx),
            'ny': str(ny)
        }

        # print(f"📡 API 요청: {base_date} {base_time} (nx={nx}, ny={ny})") # 로그 너무 많으면 주석 처리

        try:
            # 타임아웃 5초 설정 (서버 지연 방지)
            response = await asyncio.to_thread(
                requests.get,
                self.base_url,
                params=params,
                timeout=5,
            )
            
            if response.status_code != 200:
                return []

            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            return items
            
        except Exception as e:
            print(f"❌ API Fail: {e}")
            return []
