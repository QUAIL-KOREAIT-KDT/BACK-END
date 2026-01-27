# BACK-END/app/domains/user/service.py

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.repository import UserRepository

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

    async def onboarding(self, db: AsyncSession, user_id: int, address: str, window_direction: str, indoor_temp: float = None, indoor_humidity: float = None):
        """온보딩 (정보 등록)"""
        # Repo의 update_user 기능을 재사용하여 코드를 줄입니다.
        user = await self.repo.update_user(
            db, user_id,
            address=address,
            window_direction=window_direction,
            indoor_temp=indoor_temp,
            indoor_humidity=indoor_humidity
        )
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
    
    async def update_profile(self, db: AsyncSession, user_id: int, address: str, window_direction: str, indoor_temp: float, indoor_humidity: float):
        """내 정보 수정"""
        # 온보딩과 로직이 같다면 재사용해도 좋습니다.
        return await self.onboarding(db, user_id, address, window_direction, indoor_temp, indoor_humidity)