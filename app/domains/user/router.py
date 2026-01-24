# BACK-END/app/domains/users/router.py

from fastapi import APIRouter
from app.domains.user.schemas import UserLogin, UserProfileUpdate, UserHomeUpdate
from app.domains.user.service import UserService

router = APIRouter()
service = UserService()

@router.post("/login")
async def login(data: UserLogin):
    """카카오 간편 로그인"""
    """아직 리턴값 못정함"""
    print("카카오 간편 로그인")
    await service.login_kakao(data.kakao_token)
    return {"token": "dummy_jwt_token", "user_id": 1}

@router.post("/logout")
async def logout(data: UserLogin):
    """카카오 간편 로그아웃"""\
    """아직 리턴값 못정함"""
    print("카카오 간편 로그아웃")
    await service.logout_kakao(data.kakao_token)
    return {"status": "success"}

@router.delete("/withdraw")
async def withdraw():
    """희원 탈퇴!!(ㅋㅋㅋ)"""
    """아직 리턴값 못정함"""
    await service.withdraw_user(1)
    return {"status": "success"}

@router.post("/onboarding")
async def onboarding(data: UserProfileUpdate):
    """온보딩 정보 기입"""
    await service.onboarding(data.userid, data.address, data.window_direction)
    return {
        "status": "success", 
    }

@router.get("/me")
async def get_user_info(data: UserLogin):
    """내 정보 조회"""
    await service.me(data.userid)
    return {
        "user_id": 1,
        "address": "서울특별시 강남구 역삼동",
        "window_direction": "남향",
        "indoor_temp": 22.5,
        "indoor_humidity": 55
    }

@router.put("/profile-info")
async def update_profile(data: UserProfileUpdate):
    """내 정보 수정"""
    await service.update_profile(data.userid, data.address, data.window_direction, data.indoor_temp, data.indoor_humidity)
    return {"status": "success"}

@router.put("/home-info")
async def update_home(data: UserHomeUpdate):
    """집 정보 수정"""
    await service.update_home(data.userid)
    return {"status": "success"}