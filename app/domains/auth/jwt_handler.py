# app/domains/auth/jwt_handler.py

from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
# [수정 1] OAuth2PasswordBearer 대신 HTTPBearer, HTTPAuthorizationCredentials 임포트
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
import secrets
import hashlib

# OAuth2PasswordBearer 대신 HTTPBearer 사용
security = HTTPBearer()  # (단순 토큰 입력창 생성)

def create_access_token(data: dict):
    """JWT 토큰 생성 (로그인 시 사용) - 기존과 동일"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

#  refresh 토큰 생성(랜덤 문자열)
def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)

#  refresh 토큰 해시(서버 SECRET 섞어서)
def hash_refresh_token(refresh_token: str) -> str:
    raw = (refresh_token + settings.SECRET_KEY).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# 토큰 검증 및 아이디 불러오기
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    API 요청 시 토큰이 유효한지 검사
    """
    # HTTPBearer는 토큰을 'Bearer <token>' 형태로 추출해서 credentials.credentials에 담아줍니다.
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="자격 증명을 검증할 수 없습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except JWTError:
        raise credentials_exception