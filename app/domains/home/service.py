# BACK-END/app/domains/home/service.py

from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.home.models import Weather
from app.domains.user.models import User
from app.domains.home.client import WeatherClient
from app.domains.home.schemas import WeatherDetail, VentilationTime, HomeResponse

class WeatherService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = WeatherClient()

    async def get_home_info(self, user_id: int) -> HomeResponse:
        # 1. 사용자 정보 및 좌표 확인
        user = await self._get_user(user_id)
        if not user or not user.grid_nx or not user.grid_ny:
            # 좌표 없으면 기본값 (서울 종로구)
            nx, ny = 60, 127
            address = "서울특별시 종로구 (기본설정)"
        else:
            nx, ny = user.grid_nx, user.grid_ny
            address = user.region_address or "알 수 없는 지역"

        # 2. 데이터 최신화 (DB에 없으면 API 호출)
        await self._ensure_weather_data(nx, ny)

        # 3. 조회 시간 설정 (현재 ~ 내일 밤)
        now = datetime.now()
        tomorrow_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)

        # 4. DB 조회
        query = select(Weather).where(
            Weather.nx == nx,
            Weather.ny == ny,
            Weather.date >= now,
            Weather.date <= tomorrow_end
        ).order_by(Weather.date.asc())
        
        result = await self.db.execute(query)
        weather_list = result.scalars().all()

        # 5. [응답 1] 오늘 날씨 리스트 구성
        today_forecast = []
        today_str = now.strftime("%Y-%m-%d")
        
        for w in weather_list:
            if w.date.strftime("%Y-%m-%d") == today_str:
                cond = "쾌적"
                if w.humid > 70: cond = "습함"
                elif w.rain_prob > 50: cond = "비 올 확률 높음"

                today_forecast.append(WeatherDetail(
                    time=w.date.strftime("%H:%M"),
                    temp=w.temp,
                    humid=w.humid,
                    rain_prob=w.rain_prob,
                    condition=cond
                ))

        # 6. [응답 2] 환기 추천 알고리즘
        ventilation_recs = self._calculate_ventilation_times(weather_list)

        return HomeResponse(
            region_address=address,
            current_weather=today_forecast,
            ventilation_times=ventilation_recs
        )

    async def _get_user(self, user_id: int):
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _ensure_weather_data(self, nx: int, ny: int):
        """
        DB에 현재 시간 이후의 데이터가 있는지 확인하고, 없으면 API를 호출하여 저장합니다.
        """
        now = datetime.now()
        
        # 1. DB 캐시 확인 (1시간 뒤의 데이터가 있는지)
        check_time = now + timedelta(hours=1)
        query = select(Weather).where(
            Weather.nx == nx,
            Weather.ny == ny,
            Weather.date >= check_time
        ).limit(1)
        
        result = await self.db.execute(query)
        exists = result.scalars().first()

        if exists:
            return 

        # 2. 데이터가 없으므로 API 호출
        items = await self.client.fetch_forecast(nx, ny)
        if not items:
            return

        # 3. 데이터 가공
        grouped_data = {}
        for item in items:
            category = item['category']
            if category not in ['TMP', 'REH', 'POP']:
                continue
                
            fcst_date = item['fcstDate']
            fcst_time = item['fcstTime']
            fcst_value = item['fcstValue']
            
            key = f"{fcst_date}{fcst_time}"
            if key not in grouped_data:
                grouped_data[key] = {}
            grouped_data[key][category] = float(fcst_value)

        new_weather_objects = []
        for key, values in grouped_data.items():
            if 'TMP' in values and 'REH' in values and 'POP' in values:
                dt = datetime.strptime(key, "%Y%m%d%H%M")
                
                weather = Weather(
                    date=dt,
                    nx=nx,
                    ny=ny,
                    temp=values['TMP'],
                    humid=values['REH'],
                    rain_prob=int(values['POP']),
                    dew_point=None,
                    mold_index=None
                )
                new_weather_objects.append(weather)

        # 4. DB 저장 (Safe Update)
        if new_weather_objects:
            try:
                # [수정된 부분] 새로 받아온 데이터 중 가장 이른 시간부터 삭제
                # 이렇게 해야 'API 데이터 시간'과 '삭제 범위'가 일치하여 중복 에러가 안 납니다.
                min_date = min(w.date for w in new_weather_objects)
                
                delete_query = delete(Weather).where(
                    Weather.nx == nx,
                    Weather.ny == ny,
                    Weather.date >= min_date
                )
                await self.db.execute(delete_query)
                
                self.db.add_all(new_weather_objects)
                await self.db.commit()
                print(f"✅ 날씨 데이터 {len(new_weather_objects)}개 갱신 완료 (기준: {min_date} 이후)")
                
            except Exception as e:
                await self.db.rollback()
                print(f"❌ DB 저장 실패: {e}")

    def _calculate_ventilation_times(self, weather_data: list) -> list[VentilationTime]:
        recommendations = []
        streak = [] 
        MIN_TEMP, MAX_TEMP = -4, 27
        MAX_HUMID, MAX_RAIN = 60, 20

        for w in weather_data:
            is_good = (MIN_TEMP <= w.temp <= MAX_TEMP) and \
                      (w.humid <= MAX_HUMID) and \
                      (w.rain_prob <= MAX_RAIN)

            if is_good:
                streak.append(w)
            else:
                if len(streak) >= 2:
                    self._add_recommendation(recommendations, streak)
                streak = [] 

        if len(streak) >= 2:
            self._add_recommendation(recommendations, streak)
        return recommendations

    def _add_recommendation(self, rec_list, streak):
        start = streak[0]
        end = streak[-1]
        avg_humid = sum(d.humid for d in streak) / len(streak)
        
        rec_list.append(VentilationTime(
            date=start.date.strftime("%Y-%m-%d"),
            start_time=start.date.strftime("%H:%M"),
            end_time=end.date.strftime("%H:%M"),
            description=f"환기 찬스! (평균 습도 {int(avg_humid)}%)"
        ))