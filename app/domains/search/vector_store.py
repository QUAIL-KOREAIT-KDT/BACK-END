# BACK-END/app/domains/search/vector_store.py

import chromadb
import google.generativeai as genai
from app.core.config import settings
import logging

# 로그 설정 (터미널에 에러가 보이도록 설정)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(name="mold_wiki")

    def embed_text(self, text: str):
        try:
            # [수정] 최신 임베딩 모델 사용 ('models/' 접두사 필수)
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
                title="Mold Dictionary"
            )
            return result['embedding']
        except Exception as e:
            # [수정] 실패 시 에러 메시지를 명확하게 출력
            logger.error(f"⚠️ 임베딩 실패 (API 에러): {str(e)}")
            return None

    def add_document(self, doc_id: str, text: str, metadata: dict):
        vector = self.embed_text(text)
        if vector:
            self.collection.add(
                ids=[doc_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[metadata]
            )
            logger.info(f"✅ 벡터 저장 완료: {doc_id}")
            return True
        else:
            logger.error(f"❌ 벡터 저장 실패: {doc_id}")
            return False

    def search(self, query: str, n_results: int = 3):
        # 검색용 쿼리 임베딩 (task_type 변경)
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
            return self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results
            )
        except Exception as e:
            logger.error(f"검색어 임베딩 실패: {e}")
            return []

vector_store = VectorStore()