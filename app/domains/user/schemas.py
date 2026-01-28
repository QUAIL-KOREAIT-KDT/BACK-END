# BACK-END/app/domains/users/schemas.py

from pydantic import BaseModel
from typing import Optional, Literal

#
#=============입력================
#
class UserOnboarding(BaseModel):
    nickname: str
    address: str
    underground: Literal["underground", "semi-basement", "others"] # others 추가 추천
    window_direction: Literal["S", "N", "O"] 
    indoor_temp: float = 24.0  # 기본값 제공
    indoor_humidity: float = 50.0

# 2. [수정용] 바꾸고 싶은 것만 보냄 (전부 Optional)
class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    address: Optional[str] = None
    underground: Optional[Literal["underground", "semi-basement", "others"]] = None
    window_direction: Optional[Literal["S", "N", "O"]] = None
    indoor_temp: Optional[float] = None
    indoor_humidity: Optional[float] = None


#
# ============출력===============
#