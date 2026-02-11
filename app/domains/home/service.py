# BACK-END/app/domains/home/service.py

from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.domains.user.repository import UserRepository
from app.domains.home.models import Weather
from app.domains.home.utils import calculate_mold_risk
from app.domains.home.schemas import (
    HomeResponse, WeatherDetail, VentilationTime, MoldRiskItem
)

logger = logging.getLogger(__name__)

class HomeService:
    def __init__(self):
        self.user_repo = UserRepository()

    async def get_home_view(self, user_id: int, db: AsyncSession) -> HomeResponse:
        """
        메인 홈 화면 데이터 조회
        1. 곰팡이 위험도: 오늘 하루치 중 [최대, 최소, 현재(+1h)] 3개 반환
        2. 날씨 정보: 현재 시간 + 1시간 (Target Time) 데이터 1개만 반환
        3. 환기 정보: 오늘 하루치 중 '가장 좋고 긴 시간' 1개만 반환
        """
        # 1. 사용자 정보 조회
        user = await self.user_repo.get_user_by_id(db, user_id)
        if not user:
            return self._get_empty_response()

        direction = user.window_direction or "S"
        floor_type = user.underground or "others"
        address = user.region_address or "주소 미설정"
        nx = user.grid_nx or 60 
        ny = user.grid_ny or 127

        # 2. 시간 설정
        now = datetime.now()
        # [Target Time] 현재 시간 + 1시간 (분/초 0으로 초기화)
        target_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        # 오늘 하루 전체 범위 (00:00 ~ 23:59)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59)

        # 3. 데이터 조회 (오늘 전체 데이터 한 번에 조회)
        daily_query = select(Weather).where(
            Weather.nx == nx,
            Weather.ny == ny,
            Weather.date >= today_start,
            Weather.date <= today_end
        ).order_by(Weather.date.asc())
        daily_result = await db.execute(daily_query)
        daily_weather_list = daily_result.scalars().all()

        if not daily_weather_list:
            return self._get_empty_response(address)

        # Target Time에 해당하는 날씨 데이터 찾기
        target_weather = next((w for w in daily_weather_list if w.date == target_time), None)


        # 4. 곰팡이 위험도 계산 (Max, Min, Current)
        daily_max_item = None
        daily_min_item = None
        current_target_item = None
        last_item = None # 예보가 끊겼을 때를 대비한 마지막 아이템

        # 사용자 실내 데이터
        t_in = user.indoor_temp
        h_in = user.indoor_humidity

        for w in daily_weather_list:
            # 윈도우 호환성: f-string 사용
            time_str = f"{w.date.hour:02d}:00"
            
            # 위험도 계산
            risk_res = calculate_mold_risk(
                t_out=w.temp,
                rh_out=w.humid,
                direction=direction,
                floor_type=floor_type,
                t_in_real=t_in,
                rh_in_real=h_in
            )

            # 아이템 생성
            item = MoldRiskItem(
                time=time_str,
                score=risk_res.get("score", 0.0),
                level=risk_res.get("level", "SAFE"),
                status=risk_res.get("status", "안전"),
                type="NORMAL",
                message=risk_res.get("message", ""),
                temp_used=risk_res["details"].get("t_in", 0.0),
                humid_used=risk_res["details"].get("h_in", 0.0)
            )

            # Max/Min 갱신
            if daily_max_item is None or item.score > daily_max_item.score:
                daily_max_item = item
            
            if daily_min_item is None or item.score < daily_min_item.score:
                daily_min_item = item

            # Current (Target Time) 찾기
            if w.date == target_time:
                current_target_item = item
            
            last_item = item

        # 최종 리스트 조립 (MAX, MIN, CURRENT)
        final_risk_list = []
        
        if daily_max_item:
            m = daily_max_item.model_copy()
            m.type = "MAX"
            m.message = f"오늘 최대 위험 ({m.time})"
            final_risk_list.append(m)
            
        if daily_min_item:
            m = daily_min_item.model_copy()
            m.type = "MIN"
            m.message = f"오늘 최소 위험 ({m.time})"
            final_risk_list.append(m)
            
        if current_target_item:
            m = current_target_item.model_copy()
            m.type = "CURRENT"
            final_risk_list.append(m)
        elif last_item:
            # Target Time 데이터가 없으면 마지막 데이터 사용
            m = last_item.model_copy()
            m.type = "CURRENT"
            m.message = "금일 예보 종료"
            final_risk_list.append(m)


        # 5. 날씨 정보 (Target Time 기준 1개만)
        weather_details = []
        if target_weather:
            cond = "쾌적"
            if target_weather.humid > 70: cond = "습함"
            elif target_weather.rain_prob > 0: cond = "비"
            
            weather_details.append(WeatherDetail(
                time=f"{target_weather.date.hour:02d}:00",
                temp=target_weather.temp,
                humid=target_weather.humid,
                rain_prob=target_weather.rain_prob,
                condition=cond
            ))

        # 6. 환기 정보 (최적의 시간 1개만 선정)
        ventilation_recs = self._calculate_best_ventilation(daily_weather_list)

        return HomeResponse(
            region_address=address,
            current_weather=weather_details, 
            ventilation_times=ventilation_recs,
            risk_forecast=final_risk_list
        )

    def _get_empty_response(self, address="위치 정보 없음"):
        return HomeResponse(
            region_address=address,
            current_weather=[],
            ventilation_times=[],
            risk_forecast=[]
        )

    def _calculate_best_ventilation(self, weather_data: list) -> list[VentilationTime]:
        """
        [요구사항]
        1. 강수확률 0% (비 절대 안 옴)
        2. 습도 60% 이하
        3. 시간 넉넉하고 습도 낮은 '최고의 시간' 하나만 반환
        """
        candidates = [] 
        current_streak = []

        for w in weather_data:
            if (-5 <= w.temp <= 28) and (w.humid <= 60) and (w.rain_prob == 0):
                current_streak.append(w)
            else:
                if current_streak:
                    candidates.append(current_streak)
                    current_streak = []
        
        if current_streak:
            candidates.append(current_streak)

        if not candidates:
            return [] 

        # [정렬 기준] 1.지속시간(긴 순) 2.평균습도(낮은 순)
        best_streak = sorted(
            candidates, 
            key=lambda s: (-len(s), sum(w.humid for w in s) / len(s))
        )[0]

        s = best_streak[0]
        e = best_streak[-1]
        avg_humid = sum(w.humid for w in best_streak) / len(best_streak)
        
        end_dt = e.date + timedelta(hours=1)
        
        return [VentilationTime(
            date=s.date.strftime("%Y-%m-%d"),
            start_time=f"{s.date.hour:02d}:00",
            end_time=f"{end_dt.hour:02d}:00",
            description=f"오늘의 환기 골든타임! (평균 습도 {int(avg_humid)}%)"
        )]

home_service = HomeService()