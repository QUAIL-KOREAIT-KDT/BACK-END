# BACK-END/app/domains/user/repository.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.user.models import User

class UserRepository:
    
    # 0. 사용자 등록(완전 첫 접속)
    async def create_user(self, db: AsyncSession, kakao_id: str):
        new_user = User(kakao_id=kakao_id)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    # 2. [Read] ID로 찾기
    async def get_user_by_id(self, db: AsyncSession, user_id: int):
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # 2-1. [Read] 카카오 ID로 찾기
    async def get_user_by_kakao_id(self, db: AsyncSession, kakao_id: str):
        stmt = select(User).where(User.kakao_id == kakao_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # 3. [Update] 정보 수정 (핵심 수정!)
    async def update_user(self, db: AsyncSession, user_id: int, **kwargs):
        """
        **kwargs를 사용하여 변경된 필드만 쏙쏙 골라 업데이트합니다.
        예: await repo.update_user(db, 1, address="서울", indoor_temp=24.5)
        """
        user = await self.get_user_by_id(db, user_id)
        
        if not user:
            return None
            
        # 전달받은 키워드 인자(kwargs)를 순회하며 값 변경
        for key, value in kwargs.items():
            # User 모델에 해당 필드가 있고, 값이 None이 아닐 때만 업데이트
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        
        await db.commit()
        await db.refresh(user)
        return user

    # 4. [Delete] 회원 탈퇴
    async def delete_user(self, db: AsyncSession, user_id: int):
        user = await self.get_user_by_id(db, user_id)
        if user:
            await db.delete(user)
            await db.commit()
            return True
        return False