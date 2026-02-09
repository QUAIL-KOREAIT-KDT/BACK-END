# BACK-END/app/domains/iot/router.py

from fastapi import APIRouter, Depends, HTTPException, status
from app.domains.auth.jwt_handler import verify_token
from app.domains.iot.schemas import (
    IotDeviceListResponse,
    IotControlRequest,
    IotControlResponse,
    IotAccessCheckResponse,
)
from app.domains.iot.service import iot_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/access-check", response_model=IotAccessCheckResponse)
async def check_iot_access(user_id: int = Depends(verify_token)):
    """
    IoT 기능 접근 권한 확인

    - 마스터 유저: is_master=True
    - 일반 유저: is_master=False + 안내 메시지
    """
    is_master = iot_service.is_master_user(user_id)
    return IotAccessCheckResponse(
        is_master=is_master,
        message="IoT 기기를 제어할 수 있습니다."
        if is_master
        else "개발중인 기능입니다. 추후 업데이트 예정입니다.",
    )


@router.get("/devices", response_model=IotDeviceListResponse)
async def get_devices(user_id: int = Depends(verify_token)):
    """
    마스터 계정의 IoT 기기 목록 조회

    - 마스터 유저만 실제 기기 목록 반환
    - 일반 유저는 빈 목록 + is_master=False
    """
    is_master = iot_service.is_master_user(user_id)

    if not is_master:
        return IotDeviceListResponse(
            is_master=False,
            devices=[],
        )

    try:
        devices = await iot_service.get_devices()
        return IotDeviceListResponse(
            is_master=True,
            devices=devices,
        )
    except RuntimeError as e:
        logger.error(f"IoT 기기 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.post(
    "/devices/{device_id}/control",
    response_model=IotControlResponse,
)
async def control_device(
    device_id: str,
    body: IotControlRequest,
    user_id: int = Depends(verify_token),
):
    """
    IoT 기기 제어 (ON/OFF)

    - 마스터 유저만 제어 가능
    - 일반 유저는 403 Forbidden
    """
    if not iot_service.is_master_user(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IoT 기기 제어 권한이 없습니다.",
        )

    try:
        await iot_service.control_device(device_id, body.turn_on)
        return IotControlResponse(
            status="success",
            message=f"기기가 {'켜졌' if body.turn_on else '꺼졌'}습니다.",
            device_id=device_id,
            is_on=body.turn_on,
        )
    except RuntimeError as e:
        logger.error(f"IoT 기기 제어 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
