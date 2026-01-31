# BACK-END/test_gemini.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. .env 파일 강제 로드
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"------------ 진단 시작 ------------")

# 2. 라이브러리 버전 확인 (0.7.2 이상이어야 함)
try:
    print(f"1. 라이브러리 버전: {genai.__version__}")
except AttributeError:
    print("1. 라이브러리 버전: 확인 불가 (매우 구버전일 가능성 있음)")

# 3. API 키 확인
if not api_key:
    print("2. API 키 상태: [실패] .env에서 가져오지 못함 (None)")
else:
    print(f"2. API 키 상태: [성공] {api_key[:5]}...")
    
    # 4. 실제 연결 테스트
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("안녕 팡이? 짧게 대답해.")
        print(f"3. 모델 응답 테스트: [성공] {response.text.strip()}")
    except Exception as e:
        print(f"3. 모델 응답 테스트: [실패] {str(e)}")

print(f"------------ 진단 종료 ------------")