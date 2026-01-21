# BACK-END/app/core/lifespan.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

# 전역 객체 저장소
ml_models = {}
vector_db = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # [Startup]
    print("🚀 [System] YOLO AI 모델 및 Vector DB 로드 중...")
    # 실제 구현: ml_models["yolo"] = YOLO("app/ml_models/yolo_v8_best.pt") [Source 7]
    ml_models["yolo"] = "DUMMY_YOLO_OBJECT" 
    
    # RAG용 벡터 DB 로드 [Source 2]
    # vector_db["chroma"] = VectorStore().load()
    pass
    
    yield # 서버 실행 중
    
    # [Shutdown]
    print("🛑 [System] 리소스 해제")
    ml_models.clear()
    vector_db.clear()