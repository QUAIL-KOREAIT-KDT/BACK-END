from pydantic import BaseModel

class KakaoToken(BaseModel):
    access_token: str