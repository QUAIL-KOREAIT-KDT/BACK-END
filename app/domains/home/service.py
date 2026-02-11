# BACK-END/app/domains/home/service.py

from datetime import datetime, timedelta
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.repository import UserRepository
from app.domains.home.models import Weather
from app.domains.home.utils import calculate_mold_risk
from app.domains.home.schemas import (
    HomeResponse, WeatherDetail, VentilationTime, MoldRiskItem
)

class HomeService:
    def __init__(self):
        self.user_repo = UserRepository()

    async def get_home_view(self, user_id: int, db: AsyncSession) -> HomeResponse:
        """
        메인 홈 화면 데이터 조회
        1. 곰팡이 위험도: 오늘 하루치 중 [최대, 최소, 현재] 반환
        2. 날씨 정보: 현재 시간 + 1시간 (Target Time) 데이터 반환
        3. 환기 정보: 오늘 하루치 중 '가장 좋고 긴 시간' 반환
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
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        
        # [Target Time] 현재 시간 + 1시간 (분/초 0으로 초기화)
        target_time_aware = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        # [핵심 수정 1] 비교를 위해 타임존 정보 제거 (Naive Time)
        # DB에 저장된 날씨 데이터가 Timezone 정보가 없을 확률이 높으므로 포맷 통일
        target_time_naive = target_time_aware.replace(tzinfo=None)

        # 조회 범위 설정 (오늘 00:00 ~ 오늘 23:59)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
        query_end = now.replace(hour=23, minute=59, second=59).replace(tzinfo=None)

        # [수정 2] 밤 23시 요청 대응: Target Time이 내일 00시라면 조회 범위 확장
        if target_time_naive > query_end:
            query_end = target_time_naive

        # 3. 데이터 조회
        # DB의 date 컬럼과 비교하기 위해 타임존 없는 변수 사용 권장
        daily_query = select(Weather).where(
            Weather.nx == nx,
            Weather.ny == ny,
            Weather.date >= today_start,
            Weather.date <= query_end
        ).order_by(Weather.date.asc())
        
        daily_result = await db.execute(daily_query)
        daily_weather_list = daily_result.scalars().all()

        if not daily_weather_list:
            return self._get_empty_response(address)

        # 4. Target Weather 찾기 (타임존 무시 비교)
        target_weather = None
        for w in daily_weather_list:
            # DB 데이터(w.date)도 혹시 모르니 타임존 제거 후 비교
            w_date_naive = w.date.replace(tzinfo=None) if w.date.tzinfo else w.date
            
            if w_date_naive == target_time_naive:
                target_weather = w
                break

        # 5. 곰팡이 위험도 계산 (Max, Min, Current)
        daily_max_item = None
        daily_min_item = None
        current_target_item = None
        
        t_in = user.indoor_temp
        h_in = user.indoor_humidity

        # "오늘" 날짜 기준 (내일 00시 데이터는 통계에서 제외하고 Current용으로만 씀)
        today_day = now.day

        for w in daily_weather_list:
            time_str = f"{w.date.hour:02d}:00"
            
            risk_res = calculate_mold_risk(
                t_out=w.temp,
                rh_out=w.humid,
                direction=direction,
                floor_type=floor_type,
                t_in_real=t_in,
                rh_in_real=h_in
            )

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

            w_date_naive = w.date.replace(tzinfo=None) if w.date.tzinfo else w.date

            # Max/Min은 '오늘 날짜' 데이터 중에서만 갱신
            if w_date_naive.day == today_day:
                if daily_max_item is None or item.score > daily_max_item.score:
                    daily_max_item = item
                if daily_min_item is None or item.score < daily_min_item.score:
                    daily_min_item = item

            # [핵심 수정 3] Current Item 찾기 (타임존 무시 비교)
            if w_date_naive == target_time_naive:
                current_target_item = item

        # 최종 리스트 조립
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
            
        # [요청사항] 맨 마지막은 현재 곰팡이 위험도
        if current_target_item:
            m = current_target_item.model_copy()
            m.type = "CURRENT"
            # 메시지가 없다면 기본 상태 메시지 사용
            if not m.message:
                m.message = f"현재 상태: {m.status}"
            final_risk_list.append(m)
        else:
            # 데이터가 끊겨서 현재 시간을 못 찾은 경우 (예외 처리)
            # 마지막 데이터를 가져오거나 빈 객체라도 반환
            fallback_item = MoldRiskItem(
                time=target_time_naive.strftime("%H:00"),
                score=0, level="SAFE", status="데이터 없음", type="CURRENT",
                message="현재 날씨 정보를 불러올 수 없습니다."
            )
            final_risk_list.append(fallback_item)


        # 6. 날씨 정보 (Target Time 기준 1개)
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

        # 7. 환기 정보
        # [수정 4] 현재 시간(now) 이후 데이터만 필터링하도록 수정
        ventilation_recs = self._calculate_best_ventilation(daily_weather_list, now)

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

    def _calculate_best_ventilation(self, weather_data: list, now: datetime) -> list[VentilationTime]:
        candidates = [] 
        current_streak = []
        
        # 비교를 위해 now도 naive로 변환
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now

        for w in weather_data:
            w_date_naive = w.date.replace(tzinfo=None) if w.date.tzinfo else w.date
            
            # 현재 시간 이후만 추천 대상
            if w_date_naive <= now_naive:
                continue

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