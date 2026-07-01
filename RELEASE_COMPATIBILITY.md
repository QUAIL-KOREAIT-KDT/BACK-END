# PangPangPang Release Compatibility Plan

This backend is already used by a released mobile app. Backend changes must be
compatible with both the currently released app and the next frontend build.

## Rule

Keep existing endpoints compatible by default. Put stricter or safer behavior
behind a feature flag or a new endpoint, then switch the frontend after the
backend is already deployed.

## Current Compatibility Controls

| Area | Released app endpoint | Next-app / safe path | Default |
| --- | --- | --- | --- |
| Backend capabilities | `GET /api/meta/compat` | Same endpoint | Public manifest |
| User profile | `GET /api/users/me` | `GET /api/users/me-safe` | Existing `/me` response remains compatible |
| Search query | `GET /api/search/query` | `GET /api/search/query-safe` | Existing `/query` keeps `200` response shape |
| RAG fallback | Diagnosis RAG flow | `ENABLE_STRICT_RAG=true` | General fallback remains enabled |
| Dev login | `POST /api/auth/dev-login` | `ALLOW_DEV_LOGIN=true` only | Disabled |
| Scheduler | startup scheduler | `ENABLE_SCHEDULER=false` for local/debug | Enabled |
| Weather preload | startup weather preload | `FETCH_WEATHER_ON_STARTUP=false` for local/debug | Enabled |

## Safe Deployment Order

1. Deploy backend compatibility changes first with default flags.
2. Verify released app flows still work: login, home, diagnosis, my page,
   dictionary, fortune, game.
3. Ask the frontend owner to update the next app build to safe endpoints where
   needed, for example `/me-safe` or `/query-safe`.
4. After the new app version is widely adopted, enable stricter flags only after
   confirming old app traffic is low enough.
5. Remove old endpoints only in a later cleanup release.

## Fast Backend Update System

Backend changes are the only changes that can affect production immediately.
Use this lane for quick but controlled releases:

1. Keep released-app behavior as the default.
2. Put new behavior behind a feature flag or a new endpoint.
3. Run `scripts/backend-release-preflight.ps1` before pushing.
4. Push to GitHub only after the GitHub update log is written.
5. On EC2, pull the new commit, rebuild only the API container, and restart it.
6. Run `scripts/backend-prod-smoke.ps1` after deployment.
7. If smoke test fails, turn off the flag first. If that is not enough, roll back
   the commit and rebuild the API container.

Detailed operations are in `docs/release/BACKEND_RELEASE_SYSTEM.md`.

## Old/New App Compatibility Pattern

- Backend keeps old endpoints stable.
- Backend exposes new behavior through a new endpoint or a disabled-by-default flag.
- Frontend probes the new endpoint first only when it is backward-safe.
- If the new endpoint returns `404`, `405`, or `501`, frontend falls back to the old endpoint.
- Fallbacks should be removed only after the old Play Store app version is no longer active.

## Production Flag Guidance

Use these defaults for production while the released app is still active:

```env
ALLOW_DEV_LOGIN=false
ENABLE_STRICT_RAG=false
ENABLE_SCHEDULER=true
FETCH_WEATHER_ON_STARTUP=true
```

Before deploying with `ALLOW_DEV_LOGIN=false`, verify that the currently
released Play Store app uses real Kakao login and does not call `/auth/dev-login`.
If the released app was accidentally built without the production flag and still
depends on dev login, keep `ALLOW_DEV_LOGIN=true` only as a temporary
compatibility bridge, release a fixed app build, then turn it off.

Set `DOCS_BASIC_AUTH_USER` and `DOCS_BASIC_AUTH_PASSWORD` in the server
environment if Swagger docs should remain accessible. Do not hardcode them in
source code or Docker images.

For Firebase, keep `firebase-admin-key.json` outside the image and mount it at
runtime. `docker-compose.yml` maps the host file to
`/app/firebase-admin-key.json` read-only, so `FIREBASE_CREDENTIALS_PATH` should
point to that in-container path.

## Do Not Change Without App Coordination

- Do not remove fields from existing JSON responses.
- Do not change an existing `200` endpoint to `404`, `422`, or another status
  unless the released app is known to handle it.
- Do not change endpoint paths used by the released app.
- Do not enable `ENABLE_STRICT_RAG=true` in production until the frontend has
  been checked against empty evidence cases.
