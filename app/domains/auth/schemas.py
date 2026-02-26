# BACK-END/app/domains/auth/schemas.py

from pydantic import BaseModel
from datetime import datetime

#
#=============입력==================
#
class KakaoLoginRequest(BaseModel):
    access_token: str

# refresh
class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str                 
    token_type: str = "bearer"
    user_id: int
    is_new_user: bool
    nickname: str | None

class RefreshRequest(BaseModel):       
    refresh_token: str


#
#===============출력===================
#
class AuthResponse(BaseModel):
    """로그인 성공 시 반환할 데이터"""
    access_token: str
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"
    user_id: int
    is_new_user: bool
    nickname: str | None
    