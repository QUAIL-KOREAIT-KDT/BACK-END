# BACK-END/app/utils/fcm_service.py

import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class FCMService:
    """Firebase Cloud Messaging 푸시 알림 전송 서비스"""

    _initialized = False

    def __init__(self):
        """Firebase Admin SDK 초기화"""
        if FCMService._initialized:
            return

        if not settings.FIREBASE_CREDENTIALS_PATH:
            logger.warning("⚠️ FIREBASE_CREDENTIALS_PATH가 설정되지 않음. FCM 비활성화")
            return

        try:
            # 이미 초기화되었는지 확인
            firebase_admin.get_app()
            logger.info("Firebase already initialized")
            FCMService._initialized = True
        except ValueError:
            # 초기화 안됨 -> 새로 초기화
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
                FCMService._initialized = True
                logger.info("✅ Firebase Admin SDK 초기화 완료")
            except Exception as e:
                logger.error(f"❌ Firebase 초기화 실패: {str(e)}")

    def is_available(self) -> bool:
        """FCM 서비스 사용 가능 여부"""
        return FCMService._initialized

    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: dict = None
    ) -> bool:
        """
        단일 기기에 푸시 알림 전송

        Args:
            token: FCM 토큰
            title: 알림 제목
            body: 알림 내용
            data: 추가 데이터 (딕셔너리)

        Returns:
            bool: 전송 성공 여부
        """
        if not self.is_available():
            logger.warning("⚠️ FCM 서비스 비활성화 상태")
            return False

        try:
            # data 값들을 문자열로 변환 (FCM은 문자열만 지원)
            str_data = {}
            if data:
                for key, value in data.items():
                    str_data[key] = str(value) if value is not None else ""

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        channel_id='pangpangpang_notification',  # Android 채널 ID
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1,
                        ),
                    ),
                ),
            )

            response = messaging.send(message)
            logger.info(f"✅ FCM 전송 성공: {response}")
            return True

        except messaging.UnregisteredError:
            logger.warning(f"⚠️ 유효하지 않은 FCM 토큰: {token[:20]}...")
            return False
        except messaging.SenderIdMismatchError:
            logger.warning(f"⚠️ FCM 토큰과 프로젝트 불일치")
            return False
        except Exception as e:
            logger.error(f"❌ FCM 전송 실패: {str(e)}")
            return False

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict = None
    ) -> dict:
        """
        여러 기기에 동시 전송 (최대 500개)

        Returns:
            dict: {"success_count": int, "failure_count": int, "failed_tokens": list}
        """
        if not self.is_available():
            logger.warning("⚠️ FCM 서비스 비활성화 상태")
            return {"success_count": 0, "failure_count": len(tokens), "failed_tokens": tokens}

        if not tokens:
            return {"success_count": 0, "failure_count": 0, "failed_tokens": []}

        try:
            # data 값들을 문자열로 변환
            str_data = {}
            if data:
                for key, value in data.items():
                    str_data[key] = str(value) if value is not None else ""

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                tokens=tokens,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        channel_id='pangpangpang_notification',
                    ),
                ),
            )

            response = messaging.send_each_for_multicast(message)
            
            # 실패한 토큰 추출
            failed_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append(tokens[idx])

            logger.info(f"✅ Multicast 전송: 성공 {response.success_count}/{len(tokens)}")

            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "failed_tokens": failed_tokens,
            }
        except Exception as e:
            logger.error(f"❌ Multicast 실패: {str(e)}")
            return {
                "success_count": 0,
                "failure_count": len(tokens),
                "failed_tokens": tokens
            }


# 싱글톤 인스턴스
fcm_service = FCMService()
