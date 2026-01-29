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
from app.core.scheduler import calculate_mold_algorithm

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
        """유저 정보 업데이트 (온보딩/수정 공용)"""
        
        address_changed = False
        if "address" in kwargs and kwargs["address"]:
            raw_address = kwargs["address"]
            
            # 1. 주소 변환 (이제 3개의 값을 받습니다)
            lat, lon, standard_addr = get_lat_lon_from_address(raw_address)
            
            if lat is not None:
                address_changed = True
                # 2. 가장 가까운 날씨 도시 찾기
                real_nx, real_ny = map_to_grid(lat, lon)
                nearest = find_nearest_city(real_nx, real_ny)
                
                # 3. 데이터 저장 분리
                # (1) address: 사용자가 입력한 그대로 (상세주소 포함 가능)
                kwargs["address"] = raw_address
                
                # (2) region_address: 카카오가 깔끔하게 정리해준 주소 (예: 경기 안산시 상록구 사동)
                # -> 홈 화면 상단에 "안산시 상록구 날씨" 처럼 보여줄 때 사용
                kwargs["region_address"] = standard_addr
                
                # (3) 좌표 정보
                kwargs["latitude"] = lat
                kwargs["longitude"] = lon
                kwargs["grid_nx"] = nearest["nx"] # 날씨는 '수원' 데이터를 쓰더라도
                kwargs["grid_ny"] = nearest["ny"]
                
                print(f"✅ 유저 위치 설정: 입력('{raw_address}') -> 표준('{standard_addr}') -> 날씨매칭('{nearest['name']}')")
                
            else:
                # 주소 못 찾으면 업데이트에서 제외하거나 에러 처리
                print(f"⚠️ 주소 변환 실패로 위치 정보는 업데이트되지 않음.")
                del kwargs["address"] # 잘못된 주소는 저장 안 함 (선택사항)

        user = await self.repo.update_user(db, user_id, **kwargs)
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        if address_changed and user.grid_nx and user.grid_ny:
            await self._recalculate_risk_for_new_address(db, user)
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
        
        # 3. 유저 객체와 신규 여부를 같이 반환
        return user, is_new_user
    
    async def _recalculate_risk_for_new_address(self, db: AsyncSession, user):
        print(f"🔄 [Risk Update] 주소 변경 감지! {user.nickname}님의 위험도 재계산 시작...")
        
        today = datetime.now().date()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())

        # 1. 기존 잘못된 지역의 위험도 데이터 삭제
        await db.execute(delete(MoldRisk).where(
            MoldRisk.user_id == user.id,
            MoldRisk.target_date >= start_dt
        ))

        # 2. 새 지역의 날씨 데이터가 있는지 확인
        w_res = await db.execute(select(Weather).where(
            Weather.nx == user.grid_nx,
            Weather.ny == user.grid_ny,
            Weather.date >= start_dt,
            Weather.date <= end_dt
        ))
        weather_logs = w_res.scalars().all()

        # 3. 데이터가 없거나 부족하면 API 호출 (MAJOR_CITIES 아니어도 동작하도록)
        if not weather_logs:
            print(f"⚠️ 새 지역 날씨 데이터 없음. API 긴급 호출 (nx={user.grid_nx}, ny={user.grid_ny})")
            client = WeatherClient()
            items = await client.fetch_forecast(user.grid_nx, user.grid_ny)
            
            if items:
                new_weathers = []
                grouped_data = {}
                # (1) 데이터 그룹화
                for item in items:
                    cat = item['category']
                    if cat not in ['TMP', 'REH', 'POP']: continue
                    dt_str = f"{item['fcstDate']}{item['fcstTime']}"
                    if dt_str not in grouped_data: grouped_data[dt_str] = {}
                    grouped_data[dt_str][cat] = float(item['fcstValue'])
                
                # (2) 객체 생성 및 이슬점 계산 (필수!)
                for dt_str, val in grouped_data.items():
                    if 'TMP' in val and 'REH' in val and 'POP' in val:
                        dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
                        
                        # ★ 이슬점 계산 공식 적용 (스케줄러와 동일)
                        calc_dew_point = val['TMP'] - ((100 - val['REH']) / 5)
                        
                        new_weathers.append(Weather(
                            date=dt, nx=user.grid_nx, ny=user.grid_ny,
                            temp=val['TMP'], humid=val['REH'], rain_prob=int(val['POP']),
                            dew_point=calc_dew_point  # 계산된 값 저장
                        ))
                
                if new_weathers:
                    db.add_all(new_weathers)
                    await db.commit() # 저장 확정
                    weather_logs = new_weathers # 리스트 교체
        
        # 4. 재계산 실행
        if weather_logs:
            # 이슬점이 없는 데이터(None)가 섞여 있을 경우를 대비해 필터링하거나 방어 코드
            valid_logs = [w for w in weather_logs if w.dew_point is not None]
            
            if valid_logs:
                # 최저 이슬점 찾기
                target_weather = min(valid_logs, key=lambda w: w.dew_point)
                
                # 위험도 알고리즘 호출 (public으로 바꾼 함수 사용)
                score, level, msg = calculate_mold_algorithm(user, target_weather)
                
                new_risk = MoldRisk(
                    user_id=user.id,
                    risk_score=score,
                    risk_level=level,
                    target_date=start_dt,
                    message=msg
                )
                db.add(new_risk)
                await db.commit()
                print(f"✅ [Risk Update] 재계산 완료: {level} ({score}점)")
            else:
                 print("❌ 날씨 데이터는 있으나 이슬점(dew_point) 정보가 없어 계산 실패")
        else:
            print("❌ 기상청 API에서도 데이터를 가져오지 못해 재계산 실패")
    
    
    