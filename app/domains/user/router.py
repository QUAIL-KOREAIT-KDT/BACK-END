# BACK-END/app/domains/user/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.user.schemas import UserProfileUpdate
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

# 2. 온보딩
@router.post("/onboarding")
async def onboarding(
    data: UserProfileUpdate, 
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    await service.onboarding(
        db, user_id, 
        data.address, data.window_direction, 
        data.indoor_temp, data.indoor_humidity
    )
    return {"status": "success"}

# 3. 내 정보 조회
@router.get("/me")
async def get_user_info(
    user_id: int = Depends(verify_token), 
    db: AsyncSession = Depends(get_db)
):
    return await service.me(db, user_id)

# 4. 프로필 수정
@router.put("/profile-info")
async def update_profile(
    data: UserProfileUpdate,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    # [수정 완료] 이제 service.update_profile이 존재하므로 에러가 나지 않습니다.
    await service.update_profile(
        db, user_id, 
        data.address, data.window_direction, 
        data.indoor_temp, data.indoor_humidity
    )
    return {"status": "success"}