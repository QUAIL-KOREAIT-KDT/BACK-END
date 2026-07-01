# PangPangPang Backend Release System

작성일: 2026-07-01

## 목적

프론트엔드는 Play Store 배포 지연이 있지만, 백엔드는 운영 서버에서 `git pull`과 Docker 재시작만으로 즉시 반영된다. 따라서 백엔드는 빠르게 업데이트하되 기존 출시 앱을 깨지 않도록 아래 방식으로 관리한다.

## 릴리즈 원칙

1. 기존 출시 앱이 쓰는 endpoint는 삭제하거나 응답 형식을 바꾸지 않는다.
2. 더 엄격한 동작은 새 endpoint 또는 feature flag 뒤에 둔다.
3. 운영 배포 전 preflight를 통과시킨다.
4. 운영 배포 직후 smoke test를 돌린다.
5. 문제가 나면 즉시 이전 commit으로 되돌리고 컨테이너를 재빌드/재시작한다.

## 백엔드 빠른 반영 흐름

```text
local change
  -> backend preflight
  -> GitHub push
  -> EC2 git fetch/pull
  -> docker compose build api
  -> docker compose up -d api
  -> production smoke test
  -> release log update
```

## Feature Flag 기본값

운영 기본값은 기존 출시 앱 호환성을 우선한다.

```env
ALLOW_DEV_LOGIN=false
ENABLE_STRICT_RAG=false
ENABLE_SCHEDULER=true
FETCH_WEATHER_ON_STARTUP=true
```

Swagger 문서를 운영에서 계속 열어야 한다면 아래 키를 운영 env에만 추가한다.

```env
DOCS_BASIC_AUTH_USER=<운영 문서 계정>
DOCS_BASIC_AUTH_PASSWORD=<운영 문서 비밀번호>
```

## Secret 운영 규칙

- `.env`, `.env.compose`, Firebase key, PEM 파일은 GitHub에 올리지 않는다.
- Docker image 안에 secret을 복사하지 않는다.
- Firebase Admin key는 EC2 repo root에 두고 compose volume으로 `/app/firebase-admin-key.json`에 read-only mount한다.
- `FIREBASE_CREDENTIALS_PATH`는 컨테이너 내부 경로를 가리키게 둔다.

## 배포 전 체크

로컬에서:

```powershell
.\scripts\backend-release-preflight.ps1
```

Windows 실행 정책 때문에 막히면 아래처럼 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backend-release-preflight.ps1
```

운영 서버 기준 env/key/컨테이너 상태까지 확인하려면:

```powershell
.\scripts\backend-release-preflight.ps1 -RemoteHost 15.164.214.93 -KeyPath ..\local-secrets\quail-key.pem
```

## 배포 후 체크

운영 앱에서 발급받은 access token JSON이 있으면:

```powershell
.\scripts\backend-prod-smoke.ps1 -AuthFile C:\tmp\pangpang-prod-auth.json
```

개발 로그인 호환 모드를 임시로 켠 배포에서만:

```powershell
.\scripts\backend-prod-smoke.ps1 -UseDevLogin
```

## Rollback

운영 서버에서 문제가 나면 새 기능을 flag로 먼저 끈다. 코드 자체가 문제면 이전 commit으로 되돌린다.

```bash
cd /home/ubuntu/BACK-END
git log --oneline -5
git checkout <previous-safe-commit>
docker compose build api
docker compose up -d api
docker compose logs --tail=80 api
```

문제가 해결되면 원인을 문서화하고 새 hotfix commit으로 다시 정리한다.
## Old/New App Compatibility Contract

The backend must support the released Play Store app and the next app version
at the same time.

- Never remove or change old endpoints while old app versions are active.
- Add new behavior through a new endpoint or a feature flag.
- Keep feature flags backward-compatible by default.
- Expose supported capabilities through `GET /api/meta/compat`.
- The next frontend should try the new endpoint first and fall back to the old
  endpoint when the response is `404`, `405`, or `501`.
- Remove fallback paths only after the old app version is no longer active.
