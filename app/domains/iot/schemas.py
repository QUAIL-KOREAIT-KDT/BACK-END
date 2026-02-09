# BACK-END/app/domains/iot/schemas.py

from pydantic import BaseModel


class IotDeviceResponse(BaseModel):
    """단일 IoT 기기 응답"""
    id: str
    name: str
    type: str  # plug, dehumidifier, air_conditioner, fan
    product_name: str | None = None
    is_online: bool
    is_on: bool
    icon: str | None = None


class IotDeviceListResponse(BaseModel):
    """기기 목록 응답"""
    status: str = "success"
    is_master: bool
    devices: list[IotDeviceResponse]


class IotControlRequest(BaseModel):
    """기기 제어 요청"""
    turn_on: bool


class IotControlResponse(BaseModel):
    """기기 제어 응답"""
    status: str
    message: str
    device_id: str
    is_on: bool


class IotAccessCheckResponse(BaseModel):
    """IoT 접근 권한 확인 응답"""
    is_master: bool
    message: str
