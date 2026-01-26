# BACK-END/app/domains/auth/kakao_client.py

import httpx
from fastapi import HTTPException

class KakaoClient:
    # [수정] async def로 변경하여 비동기 함수로 만듭니다.
    async def get_user_info(self, access_token: str):
        url = "https://kapi.kakao.com/v2/user/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
        }
        
        try:
            # [수정] httpx.AsyncClient를 사용하여 비동기 요청을 보냅니다.
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
            # [실패 처리 1] 카카오 토큰 만료/오류
            if response.status_code != 200:
                print(f"Kakao API Error: {response.text}")
                raise HTTPException(status_code=401, detail="유효하지 않은 카카오 토큰입니다.")
            
            # 성공
            return response.json()
            
        except httpx.RequestError:
            # [실패 처리 2] 통신 오류
            raise HTTPException(status_code=500, detail="카카오 서버와 통신할 수 없습니다.")