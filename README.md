# 🦠 QUAIL: AI Mold Diagnosis & Care Solution

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)

## 📖 Project Overview

> **"지능형 곰팡이 진단 및 생활 케어 솔루션"**

**QUAIL** 프로젝트는 사용자가 업로드한 곰팡이 이미지를 **YOLOv8** 기반 AI로 정밀 진단하고, **RAG(Retrieval-Augmented Generation)** 기술을 활용해 상황에 맞는 최적의 해결책을 제시하는 웹 서비스입니다.

단순 진단을 넘어 기상청 데이터와 연동된 **실시간 위험도 분석**과 **게이미피케이션(오늘의 팡이 운세)** 요소를 결합하여, 사용자가 지속적으로 쾌적한 주거 환경을 유지할 수 있도록 돕습니다.

---

## 🛠️ Tech Stack

| Category | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | **FastAPI** | 비동기 API 서버 구축, 의존성 주입(DI) 및 모듈화 설계 |
| **Database** | **MySQL / SQLAlchemy** | Async Session을 활용한 고성능 비동기 DB 처리 |
| **AI (Vision)** | **YOLOv8** | 곰팡이 객체 탐지 및 심각도(G1~G5) 분류 모델 |
| **AI (LLM)** | **OpenAI / ChromaDB** | 텍스트 임베딩 및 벡터 검색 기반 RAG 챗봇 구현 |
| **Infra & Storage** | **AWS S3** | 진단 이미지 및 에셋 데이터의 안전한 클라우드 저장 |

---

## 📂 Project Structure

**Domain-Driven Design (DDD)** 원칙에 따라 비즈니스 로직을 도메인별로 분리하여 유지보수성과 확장성을 극대화했습니다.

```bash
app/
├── core/                       # ⚙️ Core Configuration
│   ├── config.py               # 환경 변수 (AWS, OpenAI, DB URL) 통합 관리
│   ├── database.py             # SQLAlchemy Async Session 및 DB 커넥션 설정
│   ├── lifespan.py             # 서버 구동 시 무거운 리소스(AI 모델) 로드 최적화
│   └── security.py             # JWT 기반 인증 및 보안 로직
├── static/                     # 🖼️ Static Assets (Images, CSS)
├── domains/                    # 📦 Business Domains (Feature Modules)
│   ├── user/                   # [User] 회원가입, 로그인, 사용자 프로필 관리
│   ├── weather/                # [Weather] 기상청 API 연동 및 곰팡이 위험 지수 산출
│   ├── diagnosis/              # [Diagnosis] 이미지 업로드, YOLO 추론, 결과 로깅
│   ├── dictionary/             # [Dictionary] 곰팡이 도감 및 정적 정보 관리
│   ├── search/                 # [Search] LLM + Vector DB 기반 지능형 검색 엔진
│   └── fortune/                # [Fortune] '오늘의 팡이' 운세 서비스 
├── ml_models/                  # 🤖 Pre-trained AI Models (.pt files)
├── utils/                      # 🛠️ Utilities (AWS S3 Upload, Common Tools)             
└── main.py                     # 🚀 Application Entry Point
