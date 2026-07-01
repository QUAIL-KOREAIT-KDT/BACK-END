from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/capabilities")
async def get_capabilities():
    """Public compatibility metadata for released and next app versions."""
    return {
        "service": "pangpang-backend",
        "api_contract": "2026-07-compatible",
        "released_app_compatible": True,
        "features": {
            "auth_kakao": True,
            "auth_dev_login": settings.ALLOW_DEV_LOGIN,
            "users_me": True,
            "users_me_safe": True,
            "search_query": True,
            "search_query_safe": True,
            "strict_rag": settings.ENABLE_STRICT_RAG,
            "scheduler": settings.ENABLE_SCHEDULER,
            "weather_on_startup": settings.FETCH_WEATHER_ON_STARTUP,
        },
        "recommended_endpoints": {
            "user_profile": "/api/users/me-safe",
            "search": "/api/search/query-safe",
        },
        "fallback_endpoints": {
            "user_profile": "/api/users/me",
            "search": "/api/search/query",
        },
    }
