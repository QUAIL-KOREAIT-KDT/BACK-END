# BACK-END/app/domains/user/service.py

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.utils.location import get_lat_lon_from_address, map_to_grid, find_nearest_city
from datetime import datetime, timedelta
from sqlalchemy import select, delete, and_
from app.domains.diagnosis.models import MoldRisk
from app.domains.home.models import Weather
from app.domains.home.client import WeatherClient
from app.domains.home.utils import calculate_mold_risk
import logging

logger = logging.getLogger(__name__)

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
            await self._recalculate_max_risk(db, user)
            
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
    
    async def _recalculate_max_risk(self, db: AsyncSession, user: User):
        """
        [일일 최대 위험도 재계산 로직]
        1. 오늘 날짜의 모든 날씨 데이터 조회
        2. 시간대별 위험도 계산
        3. 개중 '최대값(Max)'을 찾아 MoldRisk 테이블에 저장
        """
        try:
            today = datetime.now().date()
            
            # 1. 기존 오늘자 위험도 데이터 삭제 (중복 방지)
            # (만약 로그성으로 쌓아야 한다면 삭제하지 않고 INSERT만 수행)
            await db.execute(
                delete(MoldRisk).where(
                    and_(
                        MoldRisk.user_id == user.id,
                        MoldRisk.target_date >= datetime.combine(today, datetime.min.time()),
                        MoldRisk.target_date <= datetime.combine(today, datetime.max.time())
                    )
                )
            )

            # 2. 오늘 날씨 데이터 전체 조회
            start_dt = datetime.combine(today, datetime.min.time())
            end_dt = datetime.combine(today, datetime.max.time())
            
            weather_query = select(Weather).where(
                and_(
                    Weather.nx == user.grid_nx,
                    Weather.ny == user.grid_ny,
                    Weather.date >= start_dt,
                    Weather.date <= end_dt
                )
            )
            result = await db.execute(weather_query)
            weather_list = result.scalars().all()

            if not weather_list:
                logger.warning(f"User {user.id}: 날씨 데이터가 없어 위험도 재계산 건너뜀")
                return

            # 3. 최대 위험도 찾기
            max_risk_data = None
            max_score = -1.0

            # 사용자 환경 설정
            direction = user.window_direction or "S"
            floor_type = user.underground or "others"
            t_in = user.indoor_temp
            h_in = user.indoor_humidity

            for w in weather_list:
                risk = calculate_mold_risk(
                    t_out=w.temp,
                    rh_out=w.humid,
                    direction=direction,
                    floor_type=floor_type,
                    t_in_real=t_in,
                    rh_in_real=h_in
                )
                
                # 최대값 갱신
                if risk['score'] > max_score:
                    max_score = risk['score']
                    max_risk_data = risk

            # 4. 저장 (최대값)
            if max_risk_data:
                new_risk = MoldRisk(
                    user_id=user.id,
                    target_date=datetime.now(), # 현재 시간 기록
                    risk_score=max_risk_data['score'],
                    risk_level=max_risk_data['level'],   # "DANGER", "WARNING", "SAFE"
                    message=max_risk_data['message']     # 메시지 저장
                )
                db.add(new_risk)
                await db.commit()
                logger.info(f"User {user.id}: 곰팡이 위험도 재계산 완료 (Max Score: {max_score})")

        except Exception as e:
            logger.error(f"위험도 재계산 중 오류 발생: {e}")
            await db.rollback()
    
    