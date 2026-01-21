# BACK-END/app/domains/users/router.py

from fastapi import APIRouter
from app.domains.user.schemas import UserLogin, UserProfileUpdate
from app.domains.user.service import UserService

router = APIRouter()
service = UserService()

@router.post("/login")
async def login(data: UserLogin):
    """[Source 3] 카카오 간편 로그인"""
    print("카카오 간편 로그인")
    await service.login_kakao(data.kakao_token)
    return {"token": "dummy_jwt_token", "user_id": 1}

@router.put("/profile")
async def update_profile(data: UserProfileUpdate):
    """[Source 3] 마이페이지 정보 기입/수정"""
    await service.update_profile(1, data.dict())
    return {"status": "success"}