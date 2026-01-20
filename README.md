app/
├── core/
│ ├── config.py # [설정] AWS S3, OpenAI Key, DB URL 관리 [Source 4, 13]
│ ├── database.py # [DB] SQLAlchemy Async Session 설정
│ ├── lifespan.py # [성능] 서버 시작 시 YOLO 및 Vector DB 로드 (메모리 관리) [Source 5]
│ └── security.py # [보안] JWT 토큰 생성 및 검증
├── static/ # [로컬 저장소] S3 실패 시 보여줄 기본 이미지, 로고 등
│ ├── images/
│ │ ├── default_mold.png # "이미지 없음" 대체용
│ │ └── logo.png
│ └── css/  
├── domains/ # ★ 도메인별 기능 모듈
│ ├── user/ # [User] 회원가입, 로그인, 마이페이지
│ │ ├── router.py # API: POST /login, PUT /profile
│ │ ├── schemas.py # DTO: 주소, 창문방향 입력 검증 [Source 1]
│ │ ├── service.py # Logic: 카카오 토큰 검증
│ │ ├── repository.py # DB: User 테이블 CRUD
│ │ └── models.py # Entity: User 테이블 정의
│ ├── weather/ # [Weather] 날씨 및 곰팡이 지수
│ │ ├── router.py # API: GET /current
│ │ ├── schemas.py # DTO: 곰팡이 지수 반환 형식
│ │ ├── service.py # Logic: 위험도(안전~위험) 산출 알고리즘 [Source 6]
│ │ ├── client.py # Adapter: 기상청 API 호출 담당 [Source 8]
│ │ └── utils.py # Math: 위경도(GPS) -> 기상청 격자(X,Y) 변환 공식 [Source 8]
│ ├── diagnosis/ # [Diagnosis] 곰팡이 진단
│ │ ├── router.py # API: POST /predict (이미지 업로드) [Source 2]
│ │ ├── schemas.py # DTO: 진단 결과(G1~G5, 솔루션) 반환 [Source 10]
│ │ ├── service.py # Logic: S3 업로드 -> AI 추론 -> DB 저장
│ │ ├── repository.py # DB: DiagnosisLogs(히스토리) 저장
│ │ ├── models.py # Entity: 로그 테이블 정의
│ │ └── ai_engine.py # AI: YOLO 모델 추론 Wrapper (이미지 전처리) [Source 5, 9]
│ ├── dictionary/ # [Dictionary] 곰팡이 도감 (RAG 지식 베이스)
│ │ ├── router.py # API: GET /list
│ │ ├── repository.py # DB: MoldDictionary(정적 데이터) 조회 [Source 10]
│ │ └── models.py # Entity: 곰팡이 이름, 특징, 해결책 테이블
│ ├── search/ # [Search] RAG 기반 검색 엔진 (AI팀 담당)
│ │ ├── router.py # API: GET /query
│ │ ├── schemas.py # DTO: 질문/답변 형식
│ │ ├── service.py # Logic: 검색(Retrieval) + 생성(Generation) 연결 [Source 13]
│ │ ├── vector_store.py # AI: 텍스트 임베딩 및 유사도 검색 (ChromaDB)
│ │ └── rag_engine.py # AI: LLM(OpenAI) 프롬프트 호출
│ └── fortune/ # [Fortune] ★ 추가됨: 오늘의 팡이 (운세) [Source 3]
│ ├── router.py # API: GET /today (흔들기 후 호출)
│ └── service.py # Logic: 랜덤 운세 점수 및 멘트 생성
├── ml_models/ # [Model] 학습된 .pt 파일 저장소 [Source 12]
├── utils/
│ ├── **init**.py
│ └── storage.py # [AWS] S3 이미지 업로드/URL 생성 로직 [Source 5]
├── main.py # [진입점] FastAPI 앱 실행 및 라우터 통합
└── Dockerfile # [배포] 서버 컨테이너 설정
🧐 구조 검토 포인트 (Checklist)
