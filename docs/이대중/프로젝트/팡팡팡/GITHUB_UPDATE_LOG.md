# 팡팡팡 BACK-END GitHub 갱신 기록

이 문서는 Notion 대신 GitHub에 함께 남기는 백엔드 변경 이력이다.

## 기록 규칙

- GitHub에 커밋하거나 push하기 전 이 문서에 변경 이력을 추가한다.
- 운영 서버 배포 영향, 기존 출시 앱 호환성, DB/S3/Firebase/API 변경 여부를 반드시 기록한다.
- 운영 배포가 필요한 경우 배포 전 확인과 롤백 방법을 같이 남긴다.
- 비밀키, 토큰, PEM, Firebase key 값은 기록하지 않는다.

## 템플릿

```md
## YYYY-MM-DD - 변경 제목

- 저장소: BACK-END
- 브랜치:
- 커밋:
- 작업자:
- 변경 목적:
- 주요 변경:
- 출시 앱 호환성 영향:
- DB/S3/Firebase 영향:
- 로컬 테스트:
- 운영 배포 여부:
- 롤백 방법:
- 주의사항:
```

## 2026-07-01 - GitHub 갱신 기록 방식 전환

- 저장소: BACK-END
- 브랜치: 확인 필요
- 커밋: 커밋 전
- 작업자: Codex / 안재원
- 변경 목적: Notion 대신 GitHub 저장소 안의 Markdown 파일로 백엔드 변경 이력을 관리하기 위함
- 주요 변경: `docs/이대중/프로젝트/팡팡팡/GITHUB_UPDATE_LOG.md` 생성
- 출시 앱 호환성 영향: 없음
- DB/S3/Firebase 영향: 없음
- 로컬 테스트: 문서 변경만 해당
- 운영 배포 여부: 없음
- 롤백 방법: 문서 파일 제거 또는 이전 커밋으로 되돌림
- 주의사항: 운영 서버 반영 전 기존 Play Store 앱이 사용하는 API를 깨지 않는지 반드시 확인

## 2026-07-01 - 백엔드 빠른 운영 반영 시스템 추가

- 저장소: BACK-END
- 브랜치: 확인 필요
- 커밋: 커밋 전
- 작업자: Codex / 안재원
- 변경 목적: 프론트 배포 지연과 별개로 백엔드 업데이트를 빠르게 반영하되, 기존 출시 앱 장애를 막기 위한 릴리즈 절차를 고정
- 주요 변경: `docs/release/BACKEND_RELEASE_SYSTEM.md`, `scripts/backend-release-preflight.ps1`, `scripts/backend-prod-smoke.ps1` 추가 및 `docker-compose.yml` Firebase key read-only mount 보강
- 출시 앱 호환성 영향: 기본 endpoint와 기본 flag는 출시 앱 호환 우선으로 유지
- DB/S3/Firebase 영향: Firebase key를 Docker image에 복사하지 않고 런타임 mount로 사용하도록 정리
- 로컬 테스트: 백엔드 AST 문법 체크 통과, 운영 smoke는 배포 후 access token 또는 임시 dev-login 조건에서 수행 필요
- 운영 배포 여부: 아직 배포 전
- 롤백 방법: 변경 commit 이전으로 되돌린 뒤 API 컨테이너 재빌드/재시작
- 주의사항: 운영 `.env.compose`의 `FIREBASE_CREDENTIALS_PATH`가 `/app/firebase-admin-key.json`을 가리키는지 확인 필요
## 2026-07-01 - 구버전/새버전 동시 지원 계약 추가

- 저장소: BACK-END
- 브랜치: 확인 필요
- 커밋: 커밋 전
- 작업자: Codex / 안재원
- 변경 목적: 기존 Play Store 앱과 다음 앱 버전이 같은 백엔드를 동시에 사용할 수 있도록 호환성 계약을 명시
- 주요 변경: `/api/meta/compat` 공개 manifest 추가, smoke test에 old/new endpoint 확인 추가, 릴리즈 문서에 fallback 정책 추가
- 출시 앱 호환성 영향: 기존 endpoint는 유지하고 새 endpoint는 추가만 하므로 출시 앱 기본 흐름 영향 없음
- DB/S3/Firebase 영향: 없음
- 로컬 테스트: backend preflight 재실행 필요
- 운영 배포 여부: 아직 배포 전
- 롤백 방법: manifest 및 문서/스크립트 변경 commit 되돌림
- 주의사항: 새 프론트는 `404/405/501`에서 기존 endpoint fallback을 유지해야 함
