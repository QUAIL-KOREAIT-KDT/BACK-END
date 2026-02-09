import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API 키가 없습니다. .env 파일을 확인해주세요.")
else:
    genai.configure(api_key=api_key)
    print(f"🔑 API Key 확인됨: {api_key[:5]}...")

print("\n====== 📡 사용 가능한 '임베딩' 모델 목록 ======")
try:
    found = False
    for m in genai.list_models():
        # 'embedContent' 기능이 있는 모델만 찾기
        if 'embedContent' in m.supported_generation_methods:
            print(f"✅ 발견: {m.name}")
            found = True
    
    if not found:
        print("⚠️ 사용 가능한 임베딩 모델이 하나도 없습니다!")
        print("   (가능성: 라이브러리가 너무 구버전이거나, API 키가 해당 기능을 지원하지 않음)")

except Exception as e:
    print(f"❌ 목록 조회 실패: {e}")
print("===============================================")