# BACK-END/app/domains/auth/schemas.py
from pydantic import BaseModel

# [Input] 프론트엔드가 보내는 데이터
class KakaoToken(BaseModel):
    access_token: str

# [Output] 서버가 돌려주는 데이터
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int