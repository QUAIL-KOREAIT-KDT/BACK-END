# 팡팡팡 웹 서비스 Nginx 배포 가이드

## 목표

- 기존 출시 모바일 앱의 `https://pangpangpangs.com/api/*` 계약은 FastAPI로 유지한다.
- 신규 웹 서비스는 `https://pangpangpangs.com/`에서 Next.js 컨테이너로 제공한다.
- EC2에서는 Next.js 빌드를 직접 수행하지 않고, 가능한 한 로컬/CI에서 만든 이미지를 pull한다.

## 라우팅 구조

```text
https://pangpangpangs.com/api/*       -> pangpang-api:8000
https://pangpangpangs.com/backend-health -> pangpang-api:8000 /
https://pangpangpangs.com/*           -> pangpang-web:3000
```

`/api`와 `/api/`는 nginx에서 웹보다 먼저 매칭한다. 이 순서가 바뀌면 모바일 앱 트래픽이 Next.js로 들어갈 수 있으므로 수정 금지.

## EC2 권장 배포

```bash
cd /path/to/BACK-END

# 1. 현재 상태 백업
cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)
cp nginx/conf.d/pangpang.conf nginx/conf.d/pangpang.conf.bak.$(date +%Y%m%d%H%M%S)

# 2. 여유 자원 확인
free -h
df -h
docker stats --no-stream

# 3. 웹 이미지는 registry에서 pull
export PANGPANG_WEB_IMAGE=<registry>/pangpang-web:<tag>
docker compose pull web

# 4. 웹 컨테이너 먼저 기동
docker compose up -d web
docker compose ps

# 5. nginx 설정 검증 후 반영
docker compose exec nginx nginx -t
docker compose restart nginx

# 6. 운영 확인
curl -I https://pangpangpangs.com
curl -s https://pangpangpangs.com/api/meta/compat
curl -s https://pangpangpangs.com/backend-health
docker compose logs --tail=100 web
docker compose logs --tail=100 nginx
docker stats --no-stream
```

## 로컬/CI 이미지 빌드

`WEB-FRONT-END`가 `BACK-END`와 같은 상위 폴더에 있을 때만 사용한다.

```bash
cd BACK-END
export PANGPANG_WEB_IMAGE=<registry>/pangpang-web:<tag>
export NEXT_PUBLIC_KAKAO_JS_KEY=<kakao-js-key>
export NEXT_PUBLIC_WEB_BASE_URL=https://pangpangpangs.com
export NEXT_PUBLIC_KAKAO_REDIRECT_URI=https://pangpangpangs.com/auth/kakao/callback
export PANGPANG_BACKEND_ORIGIN=http://api:8000

docker compose -f docker-compose.yml -f docker-compose.web-build.yml build web
docker push "$PANGPANG_WEB_IMAGE"
```

## 롤백

```bash
# 웹만 내리고 기존 API 전용 nginx로 되돌릴 때
docker compose stop web
cp nginx/conf.d/pangpang.conf.bak.<timestamp> nginx/conf.d/pangpang.conf
docker compose exec nginx nginx -t
docker compose restart nginx
```

## 주의사항

- `NEXT_PUBLIC_*` 값은 Next.js 클라이언트 번들에 빌드 시점에 들어간다. 운영용 이미지는 반드시 운영 카카오 Redirect URI와 웹 도메인 기준으로 빌드한다.
- EC2 `t3a.medium`에서는 Next.js 빌드 중 메모리가 튈 수 있으므로 운영 서버 직접 빌드는 피한다.
- `docker builder prune -af`는 빌드 캐시를 지우므로 롤백용 이미지 태그를 확인한 뒤 수행한다.
- 모바일 앱 검증은 `https://pangpangpangs.com/api/*` 호출이 정상인지 먼저 확인한다.
