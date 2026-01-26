# BACK-END/app/domains/users/router.py

from fastapi import APIRouter, Depends
from app.domains.auth.jwt_handler import verify_token
from app.domains.user.schemas import UserLogin, UserProfileUpdate, UserHomeUpdate
from app.domains.user.service import UserService

router = APIRouter()
service = UserService()

@router.delete("/withdraw")
async def withdraw():
    """희원 탈퇴!!(ㅋㅋㅋ)\n
    아직 리턴값 못정함"""
    await service.withdraw_user(1)
    return {"status": "success"}

@router.post("/onboarding")
async def onboarding(data: UserProfileUpdate, user_id: int= Depends(verify_token)):
    """온보딩 정보 기입"""
    await service.onboarding(user_id, data.address, data.window_direction, data.indoor_temp, data.indoor_humidity)
    return {
        "status": "success", 
    }

@router.get("/me")
async def get_user_info(user_id: int = Depends(verify_token)):
    """내 정보 조회"""
    await service.me(user_id)
    return {
        "user_id": 1,
        "address": "서울",
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