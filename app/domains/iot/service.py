# BACK-END/app/domains/iot/service.py

from tuya_connector import TuyaOpenAPI
from app.core.config import settings
from app.domains.iot.schemas import IotDeviceResponse
import logging

logger = logging.getLogger(__name__)

# Tuya 기기 카테고리 → 앱 타입 매핑
DEVICE_TYPE_MAP = {
    "cz": "plug",           # 스마트 플러그
    "pc": "plug",           # 멀티탭
    "kg": "plug",           # 스위치
    "cs": "dehumidifier",   # 제습기
    "kt": "air_conditioner",# 에어컨
    "fs": "fan",            # 선풍기
}


class IotService:
    def __init__(self):
        self._api: TuyaOpenAPI | None = None
        self._initialized = False

    def _ensure_initialized(self):
        """Tuya API 클라이언트 Lazy 초기화"""
        if self._initialized:
            return

        self._connect()

    def _connect(self):
        """Tuya API 연결 (초기화 또는 재연결)"""
        if not all([settings.TUYA_ACCESS_ID, settings.TUYA_ACCESS_SECRET]):
            raise RuntimeError("Tuya API 자격 증명이 설정되지 않았습니다.")

        self._api = TuyaOpenAPI(
            settings.TUYA_BASE_URL,
            settings.TUYA_ACCESS_ID,
            settings.TUYA_ACCESS_SECRET,
        )
        response = self._api.connect()
        if not response.get("success", False):
            logger.error(f"Tuya API 연결 실패: {response}")
            self._initialized = False
            raise RuntimeError("Tuya API 연결에 실패했습니다.")

        self._initialized = True
        logger.info("Tuya API 연결 성공")

    def _reconnect(self):
        """토큰 만료 등의 이유로 재연결"""
        logger.info("Tuya API 재연결 시도...")
        self._initialized = False
        self._connect()

    def is_master_user(self, user_id: int) -> bool:
        """마스터 유저(개발자) 여부 확인"""
        return (
            settings.IOT_MASTER_USER_ID is not None
            and user_id == settings.IOT_MASTER_USER_ID
        )

    def _is_token_error(self, response: dict) -> bool:
        """토큰 만료/무효 에러인지 확인"""
        code = response.get("code", 0)
        # Tuya 토큰 관련 에러 코드: 1010(토큰 무효), 1012(토큰 만료)
        return code in (1010, 1012)

    async def get_devices(self) -> list[IotDeviceResponse]:
        """마스터 Tuya 계정에 등록된 기기 목록 조회"""
        self._ensure_initialized()

        response = self._api.get(f"/v1.0/users/{settings.TUYA_UID}/devices")

        # 토큰 만료 시 재연결 후 재시도
        if not response.get("success", False) and self._is_token_error(response):
            logger.warning(f"토큰 만료 감지, 재연결 시도: code={response.get('code')}")
            self._reconnect()
            response = self._api.get(f"/v1.0/users/{settings.TUYA_UID}/devices")

        if not response.get("success", False):
            logger.error(f"기기 목록 조회 실패: {response}")
            raise RuntimeError(
                response.get("msg", "기기 목록을 가져올 수 없습니다.")
            )

        devices = []
        for device_data in response.get("result", []):
            device_id = device_data.get("id", "")
            category = device_data.get("category", "")

            # 기기 ON/OFF 상태 조회
            is_on = False
            try:
                status_response = self._api.get(
                    f"/v1.0/devices/{device_id}/status"
                )
                if status_response.get("success"):
                    for status_item in status_response.get("result", []):
                        if status_item.get("code") in (
                            "switch_1", "switch", "switch_led"
                        ):
                            is_on = bool(status_item.get("value", False))
                            break
            except Exception as e:
                logger.warning(f"기기 {device_id} 상태 조회 실패: {e}")

            device_type = DEVICE_TYPE_MAP.get(category, "plug")

            devices.append(IotDeviceResponse(
                id=device_id,
                name=device_data.get("name", "알 수 없는 기기"),
                type=device_type,
                product_name=device_data.get("product_name"),
                is_online=device_data.get("online", False),
                is_on=is_on,
                icon=None,
            ))

        return devices

    async def control_device(self, device_id: str, turn_on: bool) -> bool:
        """기기 ON/OFF 제어"""
        self._ensure_initialized()

        commands = {
            "commands": [
                {"code": "switch_1", "value": turn_on}
            ]
        }

        response = self._api.post(
            f"/v1.0/devices/{device_id}/commands",
            commands,
        )

        # 토큰 만료 시 재연결 후 재시도
        if not response.get("success", False) and self._is_token_error(response):
            logger.warning(f"토큰 만료 감지, 재연결 후 기기 제어 재시도: {device_id}")
            self._reconnect()
            response = self._api.post(
                f"/v1.0/devices/{device_id}/commands",
                commands,
            )

        if not response.get("success", False):
            logger.error(f"기기 제어 실패 ({device_id}): {response}")
            raise RuntimeError(
                response.get("msg", "기기 제어에 실패했습니다.")
            )

        logger.info(
            f"기기 제어 성공: {device_id} -> {'ON' if turn_on else 'OFF'}"
        )
        return True


# 싱글톤 인스턴스
iot_service = IotService()
