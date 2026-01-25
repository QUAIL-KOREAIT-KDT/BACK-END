#  BACK-END/app/domains/auth/service.py

from app.domains.auth.kakao_client import KakaoClient
from app.domains.auth.jwt_handler import create_access_token
# from app.domains.user.repository import UserRepository (나중에 DB 연결 시 사용)

class AuthService:
    def __init__(self):
        self.kakao_client = KakaoClient()
    
    async def login(self, kakao_access_token: str):
        # 1. 카카오 서버에서 유저 정보 가져오기
        # kakao_user = self.kakao_client.get_user_info(kakao_access_token)
        
        # 2. 카카오 유저 ID 추출 (고유 식별자)
        # kakao_id = str(kakao_user.get("id"))
        
        # 3. [TODO] DB 작업 (회원가입/로그인)
        # 실제로는 여기서 DB를 조회해서 유저가 없으면 저장(Insert)해야 합니다.
        # user = user_repo.find_by_kakao_id(kakao_id)
        # if not user:
        #     user = user_repo.create(...)
        
        # (테스트를 위해 카카오 ID를 바로 사용)
        # user_id = kakao_id 
        user_id = 1

        # 4. [성공 처리] 우리 서버 전용 JWT 토큰 발급
        # sub에 user_id를 담아서 누구인지 식별할 수 있게 합니다.
        access_token = create_access_token(data={"sub": str(user_id)})
        print(access_token)
        return {
        "access_token": access_token,
        "user_id": user_id
    }