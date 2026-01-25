# BACK-END/app/domains/users/service.py

class UserService:
    async def withdraw_user(self, user_id: int):
        # 회원 탈퇴 및 데이터 삭제
        pass
    
    async def onboarding(self, user_id: int, address: str, window_direction: str):
        # 온보딩 정보(주소, 창문방향) DB 저장
        pass

    async def me(self, user_id: int):
        #내 정보 조회
        pass

    async def update_profile(self, user_id: int, data: dict):
        # 마이페이지 정보(주소, 창문방향) DB 업데이트
        pass
    
    async def update_home(self, user_id: int):
        # 집 정보 수정
        pass