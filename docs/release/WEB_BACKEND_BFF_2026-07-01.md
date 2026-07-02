# PangPangPang Web Backend BFF Plan

작성일: 2026-07-01

## 목적

모바일 앱은 이미 Play Store에 배포되어 있으므로 기존 `/api/*` 계약을 깨면 안 된다. 웹서비스는 화면 구조, 카카오 OAuth 콜백, 대시보드 집계, 사전 검색, 진단 업로드 UX가 모바일과 다르기 때문에 별도의 웹 전용 백엔드 레이어를 둔다.

이번 변경은 기존 모바일 API를 수정하지 않고 `/api/web/*` 네임스페이스를 추가하는 방식이다.

## 적용 원칙

- 기존 모바일 API: `/api/auth/*`, `/api/users/*`, `/api/diagnosis/*`, `/api/dictionary/*`, `/api/game/*`, `/api/my_page/*` 유지
- 웹 전용 API: `/api/web/*` 추가
- 같은 카카오 계정은 기존 `UserService.login_via_kakao()`를 재사용해 같은 `user_id`로 연결
- 웹 화면이 필요한 집계 응답은 BFF에서 묶어서 제공
- 모바일 앱과 웹은 같은 DB, S3, 진단 기록, 게임 점수, 랭킹 데이터를 공유

## 추가된 웹 API

| Endpoint | Method | Auth | 목적 |
| --- | --- | --- | --- |
| `/api/web/auth/kakao/authorize-url` | GET | Public | 웹 카카오 OAuth 인가 URL 생성 |
| `/api/web/auth/kakao/code` | POST | Public | 카카오 authorization code를 서버 JWT/refresh token으로 교환 |
| `/api/web/me/dashboard` | GET | Bearer | 프로필, 진단 기록, 게임 랭킹, 알림 설정, 요약 정보 조회 |
| `/api/web/dictionary` | GET | Bearer | 곰팡이 사전 목록, 검색, 라벨/장소 필터 |
| `/api/web/dictionary/{dictionary_id}` | GET | Bearer | 곰팡이 사전 상세 |
| `/api/web/diagnosis/predict` | POST | Bearer | 웹 이미지 업로드 진단, S3/AI/DB 저장 결과 반환 |

## 왜 BFF가 필요한가

웹은 모바일보다 한 화면에 보여줄 정보가 많다. 예를 들어 마이페이지는 프로필, 진단 기록, 게임 점수, 랭킹, 알림 설정을 한 번에 보여줘야 한다. 웹이 기존 모바일 API 여러 개를 직접 조합하면 화면마다 호출 순서와 에러 처리가 흩어진다.

BFF는 그 조합 책임을 백엔드에 모아둔다. 프론트는 화면 단위 API를 호출하고, 백엔드는 내부적으로 기존 도메인 서비스와 DB 모델을 재사용한다.

## 호환성

이 변경은 기존 모바일 라우터 등록 순서와 endpoint 경로를 변경하지 않는다. 웹 라우터는 `app/main.py`에서 다음처럼 별도 prefix로 등록된다.

```python
app.include_router(web_router, prefix="/api/web", tags=["Web"])
```

웹 인증 endpoint는 public이어야 하므로 라우터 전체에 전역 `verify_token` dependency를 걸지 않는다. 대신 로그인 이후 필요한 endpoint마다 `Depends(verify_token)`을 직접 둔다.

## 프론트 연동 가이드

1. 웹 로그인 버튼은 `/api/web/auth/kakao/authorize-url?redirect_uri={WEB_CALLBACK_URL}`을 호출해 카카오 인가 URL을 받는다.
2. 카카오 콜백 페이지는 `code`를 `/api/web/auth/kakao/code`로 전송한다.
3. 응답의 `access_token`, `refresh_token`, `user_id`를 웹 세션 저장소에 보관한다.
4. 마이페이지는 `/api/web/me/dashboard`를 호출한다.
5. 사전 목록은 `/api/web/dictionary?q=&label=&location=`을 호출한다.
6. 진단 업로드는 `multipart/form-data`로 `/api/web/diagnosis/predict`에 `file`, `place`를 전송한다.
7. access token 만료 시 기존 `/api/auth/refresh`를 사용한다.
8. 로그아웃은 기존 `/api/auth/logout`을 사용한다.

## 운영 설정 체크

웹 카카오 OAuth가 실제로 동작하려면 Kakao Developers에서 다음 값이 운영 웹 도메인과 일치해야 한다.

- Web platform domain
- Redirect URI
- REST API key

로컬 웹 개발을 위해 백엔드 CORS에는 `http://localhost:3000`부터 `http://localhost:3004`까지 허용했다.

## 검증 항목

- 기존 모바일 endpoint가 그대로 남아 있는지 확인
- `/api/web/auth/kakao/authorize-url`이 인가 URL을 반환하는지 확인
- 카카오 redirect URI 등록 후 `/api/web/auth/kakao/code`가 기존 사용자와 같은 `user_id`를 반환하는지 확인
- `/api/web/me/dashboard`가 로그인 사용자 기준 실제 DB 데이터를 반환하는지 확인
- `/api/web/dictionary`가 실제 DB/S3 URL 기반 데이터를 반환하는지 확인
- `/api/web/diagnosis/predict` 업로드 후 진단 기록이 모바일 마이페이지에서도 보이는지 확인
