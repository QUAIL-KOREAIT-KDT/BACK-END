# BACK-END/app/domains/user/service.py

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.repository import UserRepository
from app.utils.location import get_lat_lon_from_address, map_to_grid, find_nearest_city

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
        
        if "address" in kwargs and kwargs["address"]:
            raw_address = kwargs["address"]
            
            # 1. 주소 변환 (이제 3개의 값을 받습니다)
            lat, lon, standard_addr = get_lat_lon_from_address(raw_address)
            
            if lat is not None:
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
    
    
    
    