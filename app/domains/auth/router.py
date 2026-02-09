# BACK-END/app/domains/auth/router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# [중요] DB 세션과 진짜 유저 서비스를 가져옵니다.
from app.core.database import get_db
from app.domains.user.service import UserService 
from app.domains.auth.kakao_client import KakaoClient
from app.domains.auth.jwt_handler import create_access_token
from app.domains.auth.schemas import KakaoLoginRequest, AuthResponse

router = APIRouter()

user_service = UserService() 
kakao_client = KakaoClient() 

@router.post("/kakao", response_model=AuthResponse)
async def kakao_login(token: KakaoLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Kakao Access Token을 검증하고, DB를 조회하여 로그인/회원가입 처리 후 JWT를 발급합니다.
    """
    try:
        # 1. [Kakao] 카카오 서버에 토큰을 보내서 유저 정보(ID, 닉네임)를 가져옵니다.
        # (KakaoClient 코드가 정상적으로 구현되어 있다고 가정)
        kakao_user_info = await kakao_client.get_user_info(token.access_token)
        
        kakao_id = str(kakao_user_info.get("id"))
        # nickname = kakao_user_info.get("properties", {}).get("nickname", None) 카톡서버에서 닉네임 가져오는건데 설정안함 나중에 추가적으로 해도 됨

        # 2. [DB] 유저 서비스에게 "이 카카오 ID로 로그인해줘(없으면 가입시키고)" 라고 시킵니다.
        # user_service.login_via_kakao는 (User객체, 신규유저여부) 튜플을 반환해야 합니다. (이전 단계 참고)
        # 만약 user_service가 User 객체만 반환한다면 아래처럼 수정 필요
        user, is_new_user = await user_service.login_via_kakao(db, kakao_id)
        
        # (참고: 이전 대화에서 login_via_kakao가 (user, is_new)를 반환하도록 수정했었습니다.
        # 만약 아직 수정 안 했다면 user 객체만 넘어옵니다. 여기서는 user 객체만 있다고 가정합니다.)
        
        # 3. [JWT] 우리 서버 전용 토큰 발급
        access_token = create_access_token(data={"sub": str(user.id)})
        
        # 4. [성공 응답]
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "is_new_user": is_new_user, # user_service 로직에 따라 True/False 분기 필요
            "nickname": user.nickname
        }
        
    except Exception as e:
        print(f"Login Error: {e}")
        # 보안상 상세 에러는 숨기고 500 또는 401을 줍니다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인 처리에 실패했습니다. (카카오 토큰 만료 등)"
        )


# ============================================================
# 개발용 로그인 API - 에뮬레이터/테스트 환경에서 카카오 로그인 없이 토큰 발급
# [주의] 프로덕션 배포 시 반드시 제거하거나 비활성화하세요!
# ============================================================
@router.post("/dev-login", response_model=AuthResponse)
async def dev_login(db: AsyncSession = Depends(get_db)):
    """
    [개발 전용] 카카오 로그인 없이 테스트 계정으로 JWT 발급
    에뮬레이터나 테스트 환경에서 사용
    """
    try:
        # 테스트용 카카오 ID (고정값)
        test_kakao_id = "dev_test_user_12345"
        
        # DB에서 테스트 유저 조회/생성
        user, is_new_user = await user_service.login_via_kakao(db, test_kakao_id)
        
        # JWT 토큰 발급
        access_token = create_access_token(data={"sub": str(user.id)})
        
        print(f"[DEV LOGIN] 개발용 로그인 성공 - userId: {user.id}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "is_new_user": is_new_user,
            "nickname": user.nickname or "테스트유저"
        }
        
    except Exception as e:
        print(f"[DEV LOGIN] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"개발용 로그인 실패: {str(e)}"
        )