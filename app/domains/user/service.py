# BACK-END/app/domains/user/service.py

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.repository import UserRepository
from app.utils.location import get_lat_lon_from_address, map_to_grid, find_nearest_city
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from app.domains.diagnosis.models import MoldRisk
from app.domains.home.models import Weather
from app.domains.home.client import WeatherClient
from app.domains.home.utils import calculate_predicted_mold_risk

class UserService:
    def __init__(self):
        self.repo = UserRepository()
        
    async def withdraw_user(self, db: AsyncSession, user_id: int):
        """회원 탈퇴"""
        is_deleted = await self.repo.delete_user(db, user_id)
        if not is_deleted:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return {"status": "success", "message": "회원 탈퇴 완료"}
    
    async def me(self, db: AsyncSession, user_id: int):
        """내 정보 조회"""
        user = await self.repo.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return user

    async def update_user_info(self, db: AsyncSession, user_id: int, **kwargs):
        """유저 정보 업데이트 (온보딩/수정 공용) + 위험도 자동 재계산"""
        
        # 1. 재계산이 필요한 필드 목록 정의
        risk_factors = {'address', 'underground', 'window_direction', 'indoor_temp', 'indoor_humidity'}
        
        # 이번 요청에 위험도 영향 인자가 포함되어 있는지 확인
        should_recalculate = any(k in kwargs for k in risk_factors)
        
        if "address" in kwargs and kwargs["address"]:
            raw_address = kwargs["address"]
            lat, lon, standard_addr = get_lat_lon_from_address(raw_address)
            
            if lat is not None:
                real_nx, real_ny = map_to_grid(lat, lon)
                nearest = find_nearest_city(real_nx, real_ny)
                
                kwargs["address"] = raw_address
                kwargs["region_address"] = standard_addr
                kwargs["latitude"] = lat
                kwargs["longitude"] = lon
                kwargs["grid_nx"] = nearest["nx"]
                kwargs["grid_ny"] = nearest["ny"]
                
                print(f"✅ 유저 위치 변경: {standard_addr} ({nearest['name']})")
            else:
                print(f"⚠️ 주소 변환 실패. 기존 주소 유지.")
                del kwargs["address"]

        # 2. 정보 업데이트 수행
        user = await self.repo.update_user(db, user_id, **kwargs)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        # 3. 위험도 재계산 (조건 충족 시)
        if should_recalculate and user.grid_nx and user.grid_ny:
            await self._recalculate_risk(db, user)
            
        return user
    
    async def login_via_kakao(self, db: AsyncSession, kakao_id: str):
        """
        카카오 로그인
        Return: (user, is_new_user)
        """
        # 1. DB에서 찾아보기
        user = await self.repo.get_user_by_kakao_id(db, kakao_id)
        is_new_user = False
        
        # 2. 없으면 회원가입 (신규)
        if not user:
            user = await self.repo.create_user(db, kakao_id)
            is_new_user = True  # 신규 유저라고 표시!

        elif user and user.nickname is None:
            is_new_user = True
        # 3. 유저 객체와 신규 여부를 같이 반환
        return user, is_new_user
    
    async def _recalculate_risk(self, db: AsyncSession, user):
        """변경된 정보를 바탕으로 즉시 곰팡이 위험도 재진단"""
        print(f"🔄 [Risk Update] 정보 변경 감지! {user.nickname}님의 위험도 재계산 중...")
        
        today = datetime.now().date()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())

        # 1. 기존 데이터 삭제 (오늘 날짜 이후 데이터 리셋)
        await db.execute(delete(MoldRisk).where(
            MoldRisk.user_id == user.id,
        ))

        # 2. 해당 지역 날씨 데이터 조회
        w_res = await db.execute(select(Weather).where(
            Weather.nx == user.grid_nx,
            Weather.ny == user.grid_ny,
            Weather.date >= start_dt,
            Weather.date <= end_dt
        ))
        weather_logs = w_res.scalars().all()

        # 3. 날씨 데이터 없으면 긴급 수집 (주소가 바뀌었을 경우 대비)
        if not weather_logs:
            print(f"⚠️ 날씨 데이터 없음. API 긴급 호출 (nx={user.grid_nx}, ny={user.grid_ny})")
            client = WeatherClient()
            items = await client.fetch_forecast(user.grid_nx, user.grid_ny)
            
            if items:
                new_weathers = []
                grouped_data = {}
                for item in items:
                    cat = item['category']
                    if cat not in ['TMP', 'REH', 'POP']: continue
                    dt_str = f"{item['fcstDate']}{item['fcstTime']}"
                    if dt_str not in grouped_data: grouped_data[dt_str] = {}
                    grouped_data[dt_str][cat] = float(item['fcstValue'])
                
                for dt_str, val in grouped_data.items():
                    if 'TMP' in val and 'REH' in val and 'POP' in val:
                        dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
                        # 이슬점 계산 필수
                        calc_dew_point = val['TMP'] - ((100 - val['REH']) / 5)
                        
                        new_weathers.append(Weather(
                            date=dt, nx=user.grid_nx, ny=user.grid_ny,
                            temp=val['TMP'], humid=val['REH'], rain_prob=int(val['POP']),
                            dew_point=calc_dew_point
                        ))
                
                if new_weathers:
                    db.add_all(new_weathers)
                    await db.commit()
                    weather_logs = new_weathers
        
        # 4. 하이브리드 엔진으로 재계산
        valid_logs = [w for w in weather_logs if w.dew_point is not None]
        
        if valid_logs:
            # 최악의 조건(최저 이슬점) 선택
            target_weather = min(valid_logs, key=lambda w: w.dew_point)
            
            # [핵심 변경] 신규 엔진 호출
            risk_result = calculate_predicted_mold_risk(
                t_out=target_weather.temp,
                rh_out=target_weather.humid,
                direction=user.window_direction,
                floor_type=user.underground,
                t_in_real=user.indoor_temp,      # 사용자 입력값 반영
                rh_in_real=user.indoor_humidity  # 사용자 입력값 반영
            )
            
            new_risk = MoldRisk(
                user_id=user.id,
                risk_score=risk_result['score'],
                risk_level=risk_result['status'],
                target_date=start_dt,
                message=risk_result['message']
            )
            db.add(new_risk)
            await db.commit()
            print(f"✅ [Risk Update] 재계산 완료: {risk_result['status']} ({risk_result['score']}점)")
        else:
            print("❌ 날씨 데이터를 확보하지 못해 재계산 실패")
    
    