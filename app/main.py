# BACK-END/app/main.py
import logging  
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError # 데이터 검증
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
from fastapi.openapi.docs import get_swagger_ui_html

from app.core.logger import setup_logging
from app.middleware import APIAccessLoggerMiddleware

from app.core.lifespan import lifespan

# 라우터 임포트
from app.domains.user.router import router as user_router
from app.domains.home.router import router as home_router
from app.domains.diagnosis.router import router as diagnosis_router
from app.domains.dictionary.router import router as dictionary_router
from app.domains.search.router import router as search_router
from app.domains.fortune.router import router as fortune_router
from app.domains.auth.router import router as auth_router 
from app.domains.my_page.router import router as my_page_router
from app.domains.notification.router import router as notification_router
from app.domains.iot.router import router as iot_router
from app.domains.game.router import router as game_router

# jwt 토큰 검증 테스트
from app.domains.auth.jwt_handler import verify_token

security = HTTPBasic()
# QUAIL 팀 전용 로그인 정보 설정
ADMIN_USER = "quail_admin"
ADMIN_PASSWORD = "pang_password_2026"

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = compare_digest(credentials.username, ADMIN_USER)
    correct_password = compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="이름 또는 비밀번호가 틀렸습니다.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(
    title="QUAIL (팡팡팡)",
    description="곰팡이 예방 및 제거 솔루션 API [Source 6]",
    version="1.0.0",
    lifespan=lifespan, # [Source 1] AI 모델 로드 연결
    docs_url=None,
    redoc_url=None
)

# CORS 설정 (Flutter 웹/앱에서 API 호출 허용)
# 수정 후
origins = [
    "https://pangpangpangs.com",
    "https://www.pangpangpangs.com",
    "http://localhost:8000", # 로컬 개발용 (필요시 추가)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 우리 도메인만 허용하도록 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    APIAccessLoggerMiddleware,
)

@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="QUAIL API Docs")

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(username: str = Depends(get_current_username)):
    from fastapi.openapi.utils import get_openapi
    return get_openapi(title=app.title, version=app.version, routes=app.routes)

# 로깅 설정 활성화
setup_logging()
logger = logging.getLogger("api_monitor")

# [Source 2] 정적 파일 마운트 (로컬 이미지 서빙)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# public 라우터
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


# private 라우터
app.include_router(user_router, prefix="/api/users", tags=["Users"], dependencies=[Depends(verify_token)])
app.include_router(home_router, prefix="/api/home", tags=["home"], dependencies=[Depends(verify_token)])
app.include_router(diagnosis_router, prefix="/api/diagnosis", tags=["Diagnosis"], dependencies=[Depends(verify_token)])
app.include_router(dictionary_router, prefix="/api/dictionary", tags=["Dictionary"], dependencies=[Depends(verify_token)])
app.include_router(search_router, prefix="/api/search", tags=["RAG Search"], dependencies=[Depends(verify_token)])
app.include_router(fortune_router, prefix="/api/fortune", tags=["Fortune"], dependencies=[Depends(verify_token)])
app.include_router(my_page_router, prefix="/api/my_page", tags=["My_Page"], dependencies=[Depends(verify_token)])
app.include_router(notification_router, prefix="/api/notifications", tags=["Notifications"], dependencies=[Depends(verify_token)])
app.include_router(iot_router, prefix="/api/iot", tags=["IoT"], dependencies=[Depends(verify_token)])
app.include_router(game_router, prefix="/api/game", tags=["Game"], dependencies=[Depends(verify_token)])


@app.get("/")
def health_check():
    return {"status": "ok", "message": "QUAIL Server is Running~~!!"}
# get post put delete 


# ==========================================================
# [추가됨] 전역 에러 핸들러 설정
# ==========================================================

# 1. 예상치 못한 시스템 에러 (500 Internal Server Error)
# 코드가 터졌을 때 사용자에게는 "잠시 후 다시 시도해주세요"라고 친절하게 말하고,
# 내부 로그에는 진짜 에러 내용을 남깁니다.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"🛑 [System Error] {request.url} : {str(exc)}") # 로그 남기기 (나중에 logging으로 교체 가능)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "서버 내부 오류가 발생했습니다. 관리자에게 문의해주세요.",
            "path": str(request.url)
        },
    )

# 2. 우리가 의도한 에러 (HTTPException)
# 예: "로그인 실패", "존재하지 않는 유저" 등 개발자가 raise HTTPException(...) 한 경우
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "fail",
            "message": exc.detail,
            "code": exc.status_code
        },
        headers=exc.headers,
    )

# 3. 데이터 형식이 틀렸을 때 (Validation Error)
# 예: 나이에 "스물다섯"이라고 문자를 넣었을 때 Pydantic이 내는 에러를 깔끔하게 정리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # [추가] 운영자 로그에 상세 원인 기록
    error_details = exc.errors()
    logger.error(f"❌ VALIDATION_ERROR | {request.url} | Details: {error_details}")

    return JSONResponse(
        status_code=422,
        content={
            "status": "fail",
            "message": "입력 값이 올바르지 않습니다.",
            "details": error_details # 어떤 필드가 틀렸는지(name, age 등) 반환
        },
    )
# ==========================================================

