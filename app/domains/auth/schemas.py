# BACK-END/app/domains/auth/schemas.py

from pydantic import BaseModel

class KakaoLoginRequest(BaseModel):
    access_token: str

class AuthResponse(BaseModel):
    """로그인 성공 시 반환할 데이터"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    is_new_user: bool