# 팡팡팡 BACK-END 변경사항 정리

작성일: 2026-07-01

## 목적

현재 팡팡팡 앱은 이미 Play Store에 배포되어 있기 때문에, 백엔드 변경은 즉시 운영 사용자에게 영향을 줄 수 있다. 이번 변경은 기존 출시 앱을 깨지 않으면서 다음 프론트 버전이 사용할 수 있는 더 안전한 API와 운영 절차를 추가하기 위한 작업이다.

핵심 방향은 다음과 같다.

- 기존 앱이 사용하는 endpoint는 유지한다.
- 새 앱이 사용할 endpoint는 별도로 추가한다.
- 새 기능은 feature flag 또는 safe endpoint 뒤에 둔다.
- 운영 배포 전후로 preflight/smoke test를 수행한다.
- secret 파일은 Docker image에 복사하지 않고 런타임 mount로 관리한다.

## 주요 변경사항

### 1. 구버전/새버전 동시 지원

추가/정리된 endpoint:

- 기존 앱 유지: `GET /api/users/me`
- 새 앱 권장: `GET /api/users/me-safe`
- 기존 앱 유지: `GET /api/search/query`
- 새 앱 권장: `GET /api/search/query-safe`
- 서버 capability 확인: `GET /api/meta/compat`
- 상세 capability 확인: `GET /api/system/capabilities`

왜 했는가:

프론트는 Play Store 배포 지연이 있고, 백엔드는 운영 서버에 바로 반영된다. 따라서 백엔드가 먼저 구버전 앱과 새버전 앱을 동시에 지원해야 버전 차이로 인한 장애를 막을 수 있다.

### 2. 운영 feature flag 추가

추가된 설정:

```env
ALLOW_DEV_LOGIN=false
ENABLE_STRICT_RAG=false
ENABLE_SCHEDULER=true
FETCH_WEATHER_ON_STARTUP=true
DOCS_BASIC_AUTH_USER=
DOCS_BASIC_AUTH_PASSWORD=
```

왜 했는가:

운영에서 위험한 동작을 코드 수정 없이 켜고 끌 수 있게 하기 위해서다. 특히 `ALLOW_DEV_LOGIN`, `ENABLE_STRICT_RAG`는 출시 앱 호환성에 직접 영향이 있으므로 기본값은 보수적으로 둔다.

### 3. Swagger 문서 인증 방식 변경

기존에는 Swagger Basic Auth 계정이 코드에 하드코딩되어 있었다. 이제는 `DOCS_BASIC_AUTH_USER`, `DOCS_BASIC_AUTH_PASSWORD` 환경변수로만 열리도록 변경했다.

왜 했는가:

운영 계정 정보가 GitHub와 Docker image에 남지 않게 하기 위해서다.

### 4. Firebase key 처리 방식 변경

`Dockerfile`에서 `.env`, `firebase-admin-key.json` 복사를 제거했다. 대신 `docker-compose.yml`에서 아래 방식으로 read-only mount한다.

```yaml
volumes:
  - ./firebase-admin-key.json:/app/firebase-admin-key.json:ro
```

왜 했는가:

Firebase key 같은 secret을 Docker image에 굽는 방식은 운영 보안상 위험하다. 서버 파일로 보관하고 컨테이너에 read-only mount하는 방식이 더 안전하다.

운영 서버 확인 필요:

```env
FIREBASE_CREDENTIALS_PATH=/app/firebase-admin-key.json
```

### 5. RAG/Search 안전 경로 추가

기존 `/api/search/query`는 출시 앱 호환을 위해 기존 응답 형태를 유지한다. 새 `/api/search/query-safe`는 검증된 도감 기반 검색 결과가 없으면 명확히 실패하도록 분리했다.

왜 했는가:

현재 출시 앱은 기존 응답 형태를 기대한다. 새 앱은 더 엄격한 검증형 응답을 사용할 수 있어야 하므로 endpoint를 분리했다.

### 6. 비동기 블로킹 개선

외부 API 호출 또는 SDK 호출 중 일부를 `asyncio.to_thread()`로 감싸 이벤트 루프 블로킹을 줄였다.

대상:

- 날씨 API
- Tuya IoT API
- Firebase FCM 전송

왜 했는가:

FastAPI 서버에서 동기 외부 호출이 길어지면 다른 요청까지 지연될 수 있다. 운영 응답성을 높이기 위한 개선이다.

### 7. 진단 기록 삭제 권한 보강

진단 기록 삭제 시 `diagnosis.id`만 보지 않고 `user_id`까지 같이 확인하도록 변경했다.

왜 했는가:

다른 사용자의 진단 기록을 삭제할 수 있는 가능성을 막기 위해서다.

### 8. 배포 전/후 점검 스크립트 추가

추가 파일:

- `scripts/backend-release-preflight.ps1`
- `scripts/backend-prod-smoke.ps1`
- `docs/release/BACKEND_RELEASE_SYSTEM.md`
- `RELEASE_COMPATIBILITY.md`

왜 했는가:

백엔드는 운영에 즉시 반영되므로 수동 감각에 의존하지 않고, 반복 가능한 점검 절차가 필요하다.

## 운영 배포 전 체크리스트

1. `app/domains/system/router.py`가 커밋에 포함되어 있는지 확인한다.
2. `firebase-admin-key.json`이 운영 서버 `/home/ubuntu/BACK-END`에 존재하는지 확인한다.
3. 운영 `.env.compose`의 `FIREBASE_CREDENTIALS_PATH`가 `/app/firebase-admin-key.json`인지 확인한다.
4. 현재 Play Store 앱이 `/auth/dev-login`에 의존하지 않는지 확인한다.
5. 로컬에서 preflight를 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backend-release-preflight.ps1
```

## 운영 배포 순서

```bash
cd /home/ubuntu/BACK-END
git pull
docker compose build api
docker compose up -d api
docker compose logs --tail=80 api
```

주의:

이번 변경은 `Dockerfile`, `docker-compose.yml`이 포함되어 있으므로 단순 `docker restart pangpang-api`만으로는 충분하지 않다. 반드시 API 이미지를 다시 build해야 한다.

## 배포 후 확인

필수 확인:

- `GET https://pangpangpangs.com/`
- `GET https://pangpangpangs.com/api/meta/compat`
- 로그인
- 홈
- 도감
- 진단
- 마이페이지 진단 기록
- 게임 랭킹

가능하면 access token 파일을 준비한 뒤 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backend-prod-smoke.ps1 -AuthFile C:\tmp\pangpang-prod-auth.json
```

## 롤백 방법

문제가 발생하면 먼저 feature flag를 끈다.

- `ENABLE_STRICT_RAG=false`
- `ALLOW_DEV_LOGIN`은 출시 앱 상태에 맞게 임시 조정

코드 롤백이 필요하면:

```bash
cd /home/ubuntu/BACK-END
git log --oneline -5
git checkout <previous-safe-commit>
docker compose build api
docker compose up -d api
docker compose logs --tail=80 api
```

## 결론

이번 백엔드 변경은 바로 운영 반영 가능한 형태를 목표로 했지만, 구버전 앱과 새버전 앱의 동시 지원을 전제로 한다. 따라서 백엔드는 프론트보다 먼저 배포해도 되지만, 반드시 preflight와 smoke test를 통과시킨 뒤 진행해야 한다.
