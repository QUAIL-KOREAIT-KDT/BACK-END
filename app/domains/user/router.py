# BACK-END/app/domains/user/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.user.schemas import UserOnboarding, UserProfileUpdate
from app.domains.user.service import UserService

router = APIRouter()
service = UserService()

# 1. 회원 탈퇴
@router.delete("/withdraw")
async def withdraw(
    user_id: int = Depends(verify_token), 
    db: AsyncSession = Depends(get_db)
):
    return await service.withdraw_user(db, user_id)

# 2. 온보딩 (전체 필수 데이터 받기)
@router.post("/onboarding")
async def onboarding(
    data: UserOnboarding,  # [적용] 꽉 찬 스키마
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # 딕셔너리로 변환해서 서비스에 통째로 넘김 (**kwargs 활용)
    await service.update_user_info(db, user_id, **data.model_dump())
    return {"status": "success"}

# 3. 내 정보 조회
@router.get("/me")
async def get_user_info(
    user_id: int = Depends(verify_token), 
    db: AsyncSession = Depends(get_db)
):
    return await service.me(db, user_id)

# 4. 프로필 수정 (일부분만 수정 가능)
@router.put("/profile-info")
async def update_profile(
    data: UserProfileUpdate, # [적용] 널널한 스키마
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # 입력된 값만 걸러서(exclude_unset=True) 서비스로 넘김
    # 예: 닉네임만 보내면 닉네임만 수정됨
    update_data = data.model_dump(exclude_unset=True)
    await service.update_user_info(db, user_id, **update_data)
    return {"status": "success"}