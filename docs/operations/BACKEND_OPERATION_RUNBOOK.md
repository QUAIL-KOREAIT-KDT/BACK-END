# PangPangPang Backend Operation Runbook

## 목적

팡팡팡 백엔드는 운영 중인 모바일 앱과 신규 웹이 함께 사용하는 FastAPI 서비스다. 운영 변경 시 기존 모바일 앱의 `/api/*` 계약을 깨지 않는 것이 최우선이다.

## 코드 수정 원칙

- 기존 모바일 앱이 사용하는 엔드포인트의 응답 필드는 제거하거나 의미를 바꾸지 않는다.
- 더 엄격한 동작이나 새 화면 전용 응답은 `/api/web/*`, `*-safe`, feature flag 방식으로 추가한다.
- 카카오 로그인, 진단, 사전, 게임, 알림, 홈 위험도 API는 모바일 앱에서 이미 사용 중이므로 변경 전 호출부를 반드시 확인한다.

## 로컬 검증

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

최소 확인:

```bash
curl http://localhost:8000/
curl http://localhost:8000/api/meta/compat
```

Docker 검증:

```bash
docker compose config
docker compose up -d db api
docker compose logs --tail=100 api
```

## 운영 배포 절차

1. 서버 상태 확인
   ```bash
   free -h
   df -h
   docker compose ps
   docker stats --no-stream
   ```
2. 배포 전 백업
   ```bash
   cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)
   cp nginx/conf.d/pangpang.conf nginx/conf.d/pangpang.conf.bak.$(date +%Y%m%d%H%M%S)
   ```
3. 코드 반영
   ```bash
   git pull origin main
   docker compose build api
   docker compose up -d api
   ```
4. nginx 변경이 있을 때만
   ```bash
   docker compose exec nginx nginx -t
   docker compose restart nginx
   ```
5. 검증
   ```bash
   curl -s https://pangpangpangs.com/api/meta/compat
   curl -s https://pangpangpangs.com/backend-health
   docker compose logs --tail=100 api
   ```

## 컨테이너 재시작 기준

- 코드 변경 후: `docker compose up -d --build api`
- env 변경 후: `docker compose up -d --force-recreate api`
- nginx 설정 변경 후: `docker compose exec nginx nginx -t && docker compose restart nginx`
- DB는 특별한 사유 없이 재시작하지 않는다.

## 롤백

```bash
git log --oneline -5
git checkout <previous_commit>
docker compose up -d --build api
docker compose exec nginx nginx -t
docker compose restart nginx
```

DB 마이그레이션이나 데이터 삭제가 포함된 변경은 롤백 전에 별도 백업이 필요하다.

## 운영 확인 체크리스트

- 모바일 앱 로그인
- 모바일 앱 진단 업로드
- 모바일 앱 사전 이미지 로딩
- 웹 카카오 로그인
- 웹 홈 위험도/날씨
- 웹 진단 업로드
- `/api/meta/compat` 응답
