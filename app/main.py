# BACK-END/app/main.py

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse 
from fastapi.exceptions import RequestValidationError # 데이터 검증

from app.core.lifespan import lifespan

# 라우터 임포트
from app.domains.auth.jwt_handler import verify_token

from app.domains.user.router import router as user_router
from app.domains.home.router import router as home_router
from app.domains.diagnosis.router import router as diagnosis_router
from app.domains.dictionary.router import router as dictionary_router
from app.domains.search.router import router as search_router
from app.domains.fortune.router import router as fortune_router
from app.domains.auth.router import router as auth_router 

# jwt 토큰 검증 테스트
from app.domains.auth.jwt_handler import verify_token

app = FastAPI(
    title="QUAIL (팡팡팡)",
    description="곰팡이 예방 및 제거 솔루션 API [Source 6]",
    version="1.0.0",
    lifespan=lifespan # [Source 1] AI 모델 로드 연결
)

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
            "message": exc.detail, # 개발자가 적은 에러 메시지
            "code": exc.status_code
        },
    )

# 3. 데이터 형식이 틀렸을 때 (Validation Error)
# 예: 나이에 "스물다섯"이라고 문자를 넣었을 때 Pydantic이 내는 에러를 깔끔하게 정리
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "fail",
            "message": "입력 값이 올바르지 않습니다.",
            "details": exc.errors() # 어디가 틀렸는지 자세히 알려줌
        },
    )
# ==========================================================