import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.domains.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_token,
)
from app.domains.auth.kakao_client import KakaoClient
from app.domains.auth.router import user_service
from app.domains.auth.schemas import AuthResponse
from app.domains.diagnosis.models import Diagnosis
from app.domains.diagnosis.service import DiagnosisService
from app.domains.dictionary.models import Dictionary
from app.domains.game.service import GameService
from app.domains.my_page.service import MyPageService
from app.domains.user.service import UserService
from app.domains.web.schemas import (
    KakaoAuthorizeUrlResponse,
    KakaoCodeLoginRequest,
    WebDashboardResponse,
    WebDiagnosisResult,
    WebDictionaryItem,
)

router = APIRouter()
kakao_client = KakaoClient()
web_user_service = UserService()
game_service = GameService()
_diagnosis_guard_lock = asyncio.Lock()
_diagnosis_users_in_flight: set[int] = set()


def _dictionary_to_item(item: Dictionary) -> WebDictionaryItem:
    return WebDictionaryItem.model_validate(item)


def _matches(value: str | None, query: str) -> bool:
    return query.lower() in (value or "").lower()


async def _issue_tokens_for_kakao_id(db: AsyncSession, kakao_id: str) -> AuthResponse:
    user, is_new_user = await user_service.login_via_kakao(db, kakao_id)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token()

    user.refresh_token_hash = hash_refresh_token(refresh_token)
    user.refresh_token_expires_at = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        refresh_token_expires_at=user.refresh_token_expires_at,
        token_type="bearer",
        user_id=user.id,
        is_new_user=is_new_user,
        nickname=user.nickname,
    )


@router.get("/auth/kakao/authorize-url", response_model=KakaoAuthorizeUrlResponse)
async def kakao_authorize_url(
    redirect_uri: str = Query(...),
    state: str | None = Query(None),
):
    params = {
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    if state:
        params["state"] = state

    return KakaoAuthorizeUrlResponse(
        authorize_url=f"https://kauth.kakao.com/oauth/authorize?{urlencode(params)}",
        state=state,
    )


@router.post("/auth/kakao/code", response_model=AuthResponse)
async def kakao_code_login(
    payload: KakaoCodeLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": payload.redirect_uri,
        "code": payload.code,
    }
    if settings.KAKAO_CLIENT_SECRET:
        token_payload["client_secret"] = settings.KAKAO_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            "https://kauth.kakao.com/oauth/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kakao authorization code exchange failed.",
        )

    kakao_access_token = token_response.json().get("access_token")
    if not kakao_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kakao access token was not returned.",
        )

    kakao_user_info = await kakao_client.get_user_info(kakao_access_token)
    kakao_id = str(kakao_user_info.get("id"))
    if not kakao_id or kakao_id == "None":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kakao user id was not returned.",
        )

    return await _issue_tokens_for_kakao_id(db, kakao_id)


@router.get("/me/dashboard", response_model=WebDashboardResponse)
async def web_dashboard(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    profile = await web_user_service.me(db, user_id)
    my_page_service = MyPageService(db)
    diagnosis_history = await my_page_service.get_diagnosis_records(db, user_id)
    ranking = await game_service.get_rankings(db, user_id)
    my_best = await game_service.get_personal_best(db, user_id)

    notification_enabled = (
        profile.notification_settings if profile.notification_settings is not None else True
    )

    return {
        "profile": {
            "id": profile.id,
            "nickname": profile.nickname,
            "address": profile.address,
            "region_address": profile.region_address,
            "indoor_temp": profile.indoor_temp,
            "indoor_humidity": profile.indoor_humidity,
            "notification_settings": notification_enabled,
            "created_at": profile.created_at,
        },
        "diagnosis_history": diagnosis_history,
        "game": {
            "ranking": ranking.model_dump() if hasattr(ranking, "model_dump") else ranking,
            "my_best": my_best.model_dump() if hasattr(my_best, "model_dump") else my_best,
        },
        "notification_settings": {
            "notification_enabled": notification_enabled,
        },
        "summary": {
            "diagnosis_count": len(diagnosis_history),
            "s3_image_count": len(
                [item for item in diagnosis_history if str(item.get("image_path", "")).startswith("http")]
            ),
            "gradcam_count": len([item for item in diagnosis_history if item.get("gradcam_image_path")]),
        },
    }


@router.get("/dictionary", response_model=list[WebDictionaryItem])
async def web_dictionary_list(
    q: str | None = Query(None),
    label: str | None = Query(None),
    location: str | None = Query(None),
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Dictionary).order_by(Dictionary.label, Dictionary.name))
    items = list(result.scalars().all())

    if q:
        items = [
            item
            for item in items
            if any(
                [
                    _matches(item.name, q),
                    _matches(item.label, q),
                    _matches(item.feature, q),
                    _matches(item.location, q),
                    _matches(item.solution, q),
                    _matches(item.preventive, q),
                ]
            )
        ]
    if label:
        items = [item for item in items if item.label == label]
    if location:
        items = [item for item in items if _matches(item.location, location)]

    return [_dictionary_to_item(item) for item in items]


@router.get("/dictionary/{dictionary_id}", response_model=WebDictionaryItem)
async def web_dictionary_detail(
    dictionary_id: int,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Dictionary).where(Dictionary.id == dictionary_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Dictionary item not found.")
    return _dictionary_to_item(item)


@router.get("/diagnosis/{diagnosis_id}/public", response_model=WebDiagnosisResult)
async def web_public_diagnosis_detail(
    diagnosis_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Diagnosis result not found.")

    return {
        "id": item.id,
        "result": item.result,
        "confidence": item.confidence,
        "image_path": item.image_path,
        "gradcam_image_path": item.gradcam_image_path,
        "bbox_coordinates": item.bbox_coordinates,
        "mold_location": item.mold_location,
        "created_at": item.created_at,
        "model_solution": item.model_solution,
        "web_next": {
            "login": "/auth/kakao/callback",
            "diagnosis": "/app/diagnosis",
            "dictionary": "/app/dictionary",
        },
    }


@router.post("/diagnosis/predict", response_model=WebDiagnosisResult)
async def web_predict_mold(
    file: UploadFile = File(...),
    place: str = Form("other"),
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    allowed_places = {
        "windows",
        "wallpaper",
        "bathroom",
        "ceiling",
        "kitchen",
        "food",
        "veranda",
        "air_conditioner",
        "living_room",
        "sink",
        "toilet",
        "other",
    }
    if place not in allowed_places:
        raise HTTPException(status_code=422, detail="Invalid diagnosis place.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files can be uploaded.")

    async with _diagnosis_guard_lock:
        if user_id in _diagnosis_users_in_flight:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Diagnosis is already running for this user.",
            )
        _diagnosis_users_in_flight.add(user_id)

    try:
        service = DiagnosisService(db)
        result = await service.diagnose_image(file, place, user_id)
        return {
            "id": result.id,
            "result": result.result,
            "confidence": result.confidence,
            "image_path": result.image_path,
            "gradcam_image_path": result.gradcam_image_path,
            "bbox_coordinates": result.bbox_coordinates,
            "mold_location": result.mold_location,
            "created_at": result.created_at,
            "model_solution": result.model_solution,
            "web_next": {
                "history": "/api/web/me/dashboard",
                "detail": "/api/my_page/diagnosis-info/",
                "share_link": f"/link/diagnosis/{result.id}",
            },
        }
    finally:
        async with _diagnosis_guard_lock:
            _diagnosis_users_in_flight.discard(user_id)
