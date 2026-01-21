# BACK-END/app/domains/users/service.py

class UserService:
    async def login_kakao(self, token: str):
        # [Source 3] 카카오 API 토큰 검증 및 DB 사용자 조회/생성
        pass

    async def update_profile(self, user_id: int, data: dict):
        # [Source 3] 마이페이지 정보(주소, 창문방향) DB 업데이트
        pass
    
    async def withdraw_user(self, user_id: int):
        # [Source 3] 회원 탈퇴 및 데이터 삭제
        pass