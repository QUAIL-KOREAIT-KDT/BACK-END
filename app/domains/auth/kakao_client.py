# BACK-END/app/domains/auth/kakao_client.py

import requests
from fastapi import HTTPException

class KakaoClient:
    def get_user_info(self, access_token: str):
        # 카카오 유저 정보 요청 URL
        url = "https://kapi.kakao.com/v2/user/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
        }
        
        try:
            response = requests.get(url, headers=headers)
            
            # [실패 처리 1] 카카오 토큰이 만료되었거나 틀렸을 때
            if response.status_code != 200:
                print(f"Kakao API Error: {response.text}")
                raise HTTPException(status_code=401, detail="유효하지 않은 카카오 토큰입니다.")
            
            return response.json()
            
        except requests.exceptions.RequestException:
            # [실패 처리 2] 인터넷 연결 문제 등 통신 에러
            raise HTTPException(status_code=500, detail="카카오 서버와 통신할 수 없습니다.")