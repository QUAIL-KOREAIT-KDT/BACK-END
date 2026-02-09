# BACK-END/app/domains/home/service.py

from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.home.models import Weather
from app.domains.user.models import User
from app.domains.home.client import WeatherClient
from app.domains.home.schemas import WeatherDetail, VentilationTime, HomeResponse, RiskInfo
from app.domains.home.utils import calculate_predicted_mold_risk

class WeatherService:
    # 좌표별 마지막 API 호출에 사용된 base_time을 캐싱
    # key: (nx, ny), value: "YYYYMMDDHHMM" 형태의 base_time 문자열
    _last_fetched_base: dict[tuple[int, int], str] = {}

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

        # 3. 조회 시간 설정 (다음 정시 ~ 내일 밤)
        now = datetime.now()
        # 현재 시간의 다음 정시를 기준으로 조회 (예: 09:30 → 10:00 데이터부터)
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        tomorrow_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)

        # 4. DB 조회 (다음 정시 이후 데이터)
        query = select(Weather).where(
            Weather.nx == nx,
            Weather.ny == ny,
            Weather.date >= next_hour,
            Weather.date <= tomorrow_end
        ).order_by(Weather.date.asc())
        
        result = await self.db.execute(query)
        weather_list = result.scalars().all()

        current_weather_obj = None
        if weather_list:
             # 리스트는 시간순 정렬되어 있으므로 첫 번째가 현재와 가장 가까움
             current_weather_obj = weather_list[0]

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

        # 7. [응답 3] 실시간 곰팡이 위험도 계산 (NEW)
        risk_data = None
        if current_weather_obj and user.window_direction:
             # utils.py의 하이브리드 엔진 직접 호출
             calc_res = calculate_predicted_mold_risk(
                t_out=current_weather_obj.temp,
                rh_out=current_weather_obj.humid,
                direction=user.window_direction,
                floor_type=user.underground,
                t_in_real=user.indoor_temp,
                rh_in_real=user.indoor_humidity
             )
             
             risk_data = RiskInfo(
                 score=calc_res['score'],
                 level=calc_res['status'],
                 message=calc_res['message'],
                 details=calc_res.get('details') # 시뮬레이션 상세 수치 포함
             )

        return HomeResponse(
            region_address=address,
            current_weather=today_forecast,
            ventilation_times=ventilation_recs,
            risk_info=risk_data  # 추가된 필드 반환
        )

    async def _get_user(self, user_id: int):
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _ensure_weather_data(self, nx: int, ny: int):
        """
        DB에 현재 시간 이후의 데이터가 있는지 확인하고, 없으면 API를 호출하여 저장합니다.
        기상청 발표 주기(3시간)에 맞춰 최신 데이터를 유지합니다.
        """
        now = datetime.now()

        # 1. 현재 기상청 최신 base_time 계산 (02, 05, 08, 11, 14, 17, 20, 23시)
        if now.hour < 2:
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
            base_time = "2300"
        else:
            base_h = ((now.hour - 2) // 3) * 3 + 2
            base_date = now.strftime("%Y%m%d")
            base_time = f"{base_h:02d}00"

        current_base_key = f"{base_date}{base_time}"
        grid_key = (nx, ny)

        # 2. 이미 이 base_time으로 데이터를 가져왔으면 스킵
        if WeatherService._last_fetched_base.get(grid_key) == current_base_key:
            return

        # 3. 캐시 만료 → API 호출
        items = await self.client.fetch_forecast(nx, ny)
        if not items:
            return

        # 4. 데이터 가공
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
                )
                new_weather_objects.append(weather)

        # 5. DB 저장 (Safe Update)
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
                # 저장 성공 시 캐시 키 기록
                WeatherService._last_fetched_base[grid_key] = current_base_key
                print(f"✅ 날씨 데이터 {len(new_weather_objects)}개 갱신 완료 (base: {current_base_key})")

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