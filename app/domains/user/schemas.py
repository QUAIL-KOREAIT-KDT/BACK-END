# BACK-END/app/domains/users/schemas.py

from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    kakao_token: str

class UserProfileUpdate(BaseModel):
    userid: int
    address: str            # 기상청 연동용 주소 [Source 4]
    window_direction: str   # 남향, 동향 등 [Source 3]
    indoor_temp: Optional[float] = None
    indoor_humidity: Optional[float] = None

class UserHomeUpdate(BaseModel):
    userid: int