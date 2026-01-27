# BACK-END/app/domains/users/schemas.py

from pydantic import BaseModel
from typing import Optional, Literal

#
#=============입력================
#
class UserProfileUpdate(BaseModel):
    nickname: str
    address: str
    underground: Literal["underground", "semi-basement"]
    
    # [수정] str 대신 Literal을 사용하면 Swagger에서 드롭다운으로 선택 가능해집니다!
    # S: 남, N: 북, O: O(None)
    window_direction: Literal["S", "N", "O"] 
    
    indoor_temp: Optional[float] = None
    indoor_humidity: Optional[float] = None

class UserHomeUpdate(BaseModel):
    userid: int

#
# ============출력===============
#