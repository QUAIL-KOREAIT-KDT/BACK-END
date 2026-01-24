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

@router.get("/logout")
async def logout(data: UserLogin):
    """[Source 3] 카카오 간편 로그아웃"""
    print("카카오 간편 로그아웃")
    return {"status": "success"}

@router.get("/me")
async def get_user_info():
    """[Source 3] 내 정보 조회"""
    return {
        "user_id": 1,
        "address": "서울특별시 강남구 역삼동",
        "window_direction": "남향",
        "indoor_temp": 22.5,
        "indoor_humidity": 55
    }

@router.post("/onboarding")
async def onboarding(data: UserProfileUpdate):
    """[Source 3] 온보딩 정보 기입"""
    await service.onboarding(data.userid, data.address, data.window_direction)
    return {"status": "success"}

@router.put("/profile")
async def update_profile(data: UserProfileUpdate):
    """[Source 3] 마이페이지 정보 기입/수정"""
    await service.update_profile(data.userid, data.address, data.window_direction, data.indoor_temp, data.indoor_humidity)
    return {"status": "success"}

@router.delete("/withdraw")
async def withdraw():
    """[Source 3] 회원 탈퇴"""
    await service.withdraw_user(1)
    return {"status": "success"}