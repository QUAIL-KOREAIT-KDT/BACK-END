# BACK-END/app/domains/auth/router.py
from fastapi import APIRouter, HTTPException, status

from app.domains.auth.service import AuthService
from app.domains.search import schemas
from app.domains.auth.schemas import KakaoToken, TokenResponse
from app.domains.auth.service import AuthService

# 테스트 import
from app.domains.auth.jwt_handler import create_access_token

router = APIRouter()
service = AuthService()

# 파이썬 문법은 
# def 사용자정의 함수(인자:인자의 형식설명) 

@router.post("/kakao", response_model=TokenResponse)
async def kakao_login(token: KakaoToken):
    """
    Kakao Access Token을 받아 검증 후, 서비스 전용 JWT를 발급합니다.
    """
    try:
        # 1. 서비스 로직 호출 (카카오 검증 -> JWT 발급)
        jwt_token_json = await service.login(token.access_token)
        
        # 2. [성공 응답] 발급된 JWT 토큰 반환
        return {
        "access_token": jwt_token_json["access_token"],
        "token_type": "bearer",
        "user_id": jwt_token_json["user_id"]
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다."
        )