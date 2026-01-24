# BACK-END/app/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.lifespan import lifespan

# 라우터 임포트
from app.domains.user.router import router as user_router
from app.domains.home.router import router as home_router
from app.domains.diagnosis.router import router as diagnosis_router
from app.domains.dictionary.router import router as dictionary_router
from app.domains.search.router import router as search_router
from app.domains.fortune.router import router as fortune_router
from app.domains.auth.router import router as auth_router 

app = FastAPI(
    title="QUAIL (팡팡팡)",
    description="곰팡이 예방 및 제거 솔루션 API [Source 6]",
    version="1.0.0",
    lifespan=lifespan # [Source 1] AI 모델 로드 연결
)

# [Source 2] 정적 파일 마운트 (로컬 이미지 서빙)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 라우터 등록
app.include_router(user_router, prefix="/api/users", tags=["Users"])
app.include_router(home_router, prefix="/api/home", tags=["home"])
app.include_router(diagnosis_router, prefix="/api/diagnosis", tags=["Diagnosis"])
app.include_router(dictionary_router, prefix="/api/dictionary", tags=["Dictionary"])
app.include_router(search_router, prefix="/api/search", tags=["RAG Search"])
app.include_router(fortune_router, prefix="/api/fortune", tags=["Fortune"]) # [Source 1]

app.include_router(auth_router , prefix="/auth", tags=["Auth"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "QUAIL Server is Running~~!!"}
# get post put delete 

