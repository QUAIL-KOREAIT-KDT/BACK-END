# BACK-END/app/domains/diagnosis/service.py
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.storage import StorageClient
from app.utils.cam_utils import draw_bbox_on_image
from app.domains.diagnosis.repository import DiagnosisRepository
from app.core.lifespan import ml_models  # 서버 시작 시 로드된 모델 재사용
from app.domains.search.service import search_service # [추가] RAG 서비스 임포트
import logging
import json
import io
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 예측 확률 임계치: 이 값 미만이면 "곰팡이 특정 불가"로 처리
CONFIDENCE_THRESHOLD = 60.0

# 복합 곰팡이 감지 임계치
MULTI_MOLD_SUM_THRESHOLD = 60.0        # G1~G4 확률 합이 이 값 이상이면 복합 곰팡이 후보
MULTI_MOLD_INDIVIDUAL_THRESHOLD = 15.0  # 개별 클래스가 이 값 이상이어야 유의미한 곰팡이로 표시

# 곰팡이 등급 → 한글 이름 매핑
MOLD_KOREAN_NAMES = {
    "G1": "검은곰팡이",
    "G2": "푸른곰팡이",
    "G3": "흰곰팡이",
    "G4": "붉은곰팡이",
}

class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.storage = StorageClient()
        self.repository = DiagnosisRepository(db)
        self.ai = ml_models["efficientnet"]  # lifespan에서 서버 시작 시 한 번만 로드된 인스턴스 재사용

    async def diagnose_image(self, file: UploadFile, place: str, user_id: int):
        # 파일 바이트를 먼저 메모리로 읽기 (S3 업로드 후 스트림이 닫히므로)
        file_bytes = await file.read()
        await file.seek(0)  # S3 업로드를 위해 포인터 초기화

        # 고유 UUID 생성 (원본, CAM, JSON 파일에 동일 UUID 사용)
        file_uuid = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1] if file.filename else "jpg"

        # 1. AI 모델(EfficientNet-B0) 분류 추론 + CAM 생성
        try:
            prediction = self.ai.predict_with_cam(io.BytesIO(file_bytes), generate_cam=True)
            mold_name = prediction.get("class_name", "Unknown Mold")
            probability = float(prediction.get("confidence", 0.0))
            cam_heatmap = prediction.get("cam_heatmap")
            bbox = prediction.get("bbox")
            all_probabilities = prediction.get("all_probabilities", {})

        except Exception as e:
            logger.error(f"EfficientNet 추론 실패: {e}")
            mold_name = "Unknown"
            probability = 0.0
            cam_heatmap = None
            bbox = None
            all_probabilities = {}

        # 2. 저장 라벨 결정 (S3 폴더 분류)
        storage_label = self._determine_storage_label(mold_name, probability)

        # 3. S3 업로드: 원본 이미지 (라벨 폴더)
        original_bytes_io = io.BytesIO(file_bytes)
        image_url = self.storage.upload_to_folder(
            file_bytes=original_bytes_io,
            label=storage_label,
            file_uuid=file_uuid,
            folder_type="dataset",
            content_type=file.content_type or "image/jpeg",
            file_ext=file_ext
        )

        # 4. CAM 이미지 생성 + S3 업로드 (G0, UNCLASSIFIED 제외)
        gradcam_url = None
        bbox_json_str = None

        if storage_label not in ("G0", "UNCLASSIFIED") and bbox is not None:
            # CAM 바운딩박스 이미지 생성
            cam_image_bytes = draw_bbox_on_image(file_bytes, bbox)

            # S3 업로드: CAM 이미지
            gradcam_url = self.storage.upload_to_folder(
                file_bytes=cam_image_bytes,
                label=storage_label,
                file_uuid=file_uuid,
                folder_type="gradcam",
                content_type="image/jpeg",
                file_ext="jpg"
            )

        # 5. JSON sidecar 업로드 (bbox 좌표 + 메타데이터, G0/UNCLASSIFIED 제외)
        if storage_label not in ("G0", "UNCLASSIFIED") and bbox is not None:
            bbox_data = {
                "image_id": file_uuid,
                "label": mold_name,
                "confidence": probability,
                "bbox": {
                    "x_min": bbox[0],
                    "y_min": bbox[1],
                    "x_max": bbox[2],
                    "y_max": bbox[3],
                    "format": "xyxy",
                    "image_size": [224, 224]
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "efficientnet_b0_v1.0"
            }
            self.storage.upload_json(bbox_data, label=storage_label, file_uuid=file_uuid)
            bbox_json_str = json.dumps(bbox_data, ensure_ascii=False)

        # 6. 임계치 체크: 확률이 낮으면 복합 곰팡이 또는 판별 불가
        if probability < CONFIDENCE_THRESHOLD:
            # 6-1. 복합 곰팡이 감지 시도
            multi_info = self._check_multi_mold(all_probabilities)

            if multi_info:
                # 복합 곰팡이 확정: storage_label 오버라이드
                storage_label = "MULTI"
                mold_name = "MULTI"
                probability = multi_info["total_confidence"]

                # top-1 곰팡이명으로 RAG 1회 호출
                top_mold_name = multi_info["detected_molds"][0]["class_name"]
                rag_result = await search_service.get_mold_solution_with_rag(top_mold_name, probability)

                try:
                    rag_data = json.loads(rag_result["rag_solution"])
                    # 진단 텍스트 앞에 복합 곰팡이 안내 삽입
                    display_text = multi_info["display_name"] + "가 함께 검출되었습니다. 여러 곰팡이가 핀 것으로 확인됩니다."
                    rag_data["diagnosis"] = display_text + "\n\n" + rag_data.get("diagnosis", "")
                    rag_data["multi_mold_detail"] = {
                        "detected_molds": [
                            {"grade": m["grade"], "name": m["name"], "confidence": m["confidence"]}
                            for m in multi_info["detected_molds"]
                        ],
                        "total_confidence": multi_info["total_confidence"]
                    }
                    final_solution = json.dumps(rag_data, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    final_solution = rag_result["rag_solution"]

                # MULTI는 CAM + JSON sidecar 생성 (top-1 기준 bbox 이미 계산됨)
                if bbox is not None:
                    cam_image_bytes = draw_bbox_on_image(file_bytes, bbox)
                    gradcam_url = self.storage.upload_to_folder(
                        file_bytes=cam_image_bytes,
                        label=storage_label,
                        file_uuid=file_uuid,
                        folder_type="gradcam",
                        content_type="image/jpeg",
                        file_ext="jpg"
                    )
                    bbox_data = {
                        "image_id": file_uuid,
                        "label": multi_info["display_name"],
                        "confidence": probability,
                        "bbox": {
                            "x_min": bbox[0], "y_min": bbox[1],
                            "x_max": bbox[2], "y_max": bbox[3],
                            "format": "xyxy", "image_size": [224, 224]
                        },
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "model_version": "efficientnet_b0_v1.0"
                    }
                    self.storage.upload_json(bbox_data, label=storage_label, file_uuid=file_uuid)
                    bbox_json_str = json.dumps(bbox_data, ensure_ascii=False)

                # MULTI용 S3 원본 이미지 재업로드 (기존 UNCLASSIFIED → MULTI 폴더로)
                original_bytes_io = io.BytesIO(file_bytes)
                image_url = self.storage.upload_to_folder(
                    file_bytes=original_bytes_io,
                    label=storage_label,
                    file_uuid=file_uuid,
                    folder_type="dataset",
                    content_type=file.content_type or "image/jpeg",
                    file_ext=file_ext
                )
            else:
                # 6-2. 복합 곰팡이 아님 → 기존 UnClassified 처리
                mold_name = "UnClassified"
                final_solution = json.dumps({
                    "diagnosis": "AI가 곰팡이를 특정하지 못했습니다. 이미지의 화질이 낮거나, 곰팡이가 아닌 오염물일 수 있습니다.",
                    "FrequentlyVisitedAreas": [],
                    "solution": [
                        "곰팡이 의심 부위를 가까이 접근하여 다시 사진을 찍어보세요.",
                        "밝은 빛 아래에서 촬영하세요.",
                        "반사가 심한 경우 각도를 바꿔 다시 시도해보세요."
                    ],
                    "prevention": [],
                    "insight": "신뢰도가 낮아 정확한 곰팡이 종류를 판별할 수 없었습니다. 위의 권장 조치를 따라 다시 진단을 시도해주세요."
                }, ensure_ascii=False)
        elif mold_name == "G0_NotMold":
            # 7-1. G0 확신: 곰팡이가 아님 (RAG 호출 불필요)
            final_solution = json.dumps({
                "diagnosis": "AI 분석 결과, 해당 이미지에서 곰팡이가 감지되지 않았습니다.",
                "FrequentlyVisitedAreas": [],
                "solution": [
                    "현재 촬영하신 부분에는 곰팡이가 발견되지 않았습니다.",
                    "다른 의심 부위가 있다면 추가 진단을 진행해보세요.",
                    "곰팡이와 유사한 얼룩이나 오염물일 수 있으니, 지속적으로 관찰해주세요."
                ],
                "prevention": [
                    "실내 습도를 50% 이하로 유지하면 곰팡이 예방에 효과적입니다.",
                    "환기를 자주 시켜 공기 순환을 유지하세요.",
                    "결로가 생기기 쉬운 곳은 주기적으로 확인해주세요."
                ],
                "insight": "곰팡이가 아닌 것으로 판단되었습니다. 다만 비슷해 보이는 오염물이 시간이 지나며 곰팡이로 발전할 수 있으니 주기적으로 관찰하시길 권장합니다."
            }, ensure_ascii=False)
        else:
            # 7-2. G3 특별 처리: "물 테스트" 안내 추가
            if mold_name == "G3_WhiteMold":
                final_solution = await self._handle_g3_white_mold(mold_name, probability)
            else:
                # 기존 RAG 파이프라인 유지 (G1, G2, G4)
                rag_result = await search_service.get_mold_solution_with_rag(mold_name, probability)
                final_solution = rag_result["rag_solution"]

        # 8. DB 저장을 위한 데이터 구성
        # result 필드: "G1_Stachybotrys" → "G1" 등 등급 접두사만 저장 (프론트 표시용)
        grade = mold_name.split("_")[0]  # "G1_Stachybotrys" → "G1", "UnClassified" → "UnClassified"

        diagnosis_data = {
            "user_id": user_id,
            "image_path": image_url,
            "gradcam_image_path": gradcam_url,        # CAM 이미지 S3 URL (G0는 None)
            "bbox_coordinates": bbox_json_str,         # bbox JSON string
            "result": grade,                           # 등급 접두사 (G1~G4 / UnClassified)
            "confidence": probability,                 # 확률
            "mold_location": place,                    # 발견 장소 (사용자 입력)
            "model_solution": final_solution           # RAG가 생성한 리포트 저장
        }

        # 9. DB 저장
        saved_diagnosis = await self.repository.create_diagnosis(diagnosis_data)

        return saved_diagnosis

    def _determine_storage_label(self, mold_name: str, confidence: float) -> str:
        """
        S3 저장 폴더 라벨 결정
        - confidence < 60%: UNCLASSIFIED (신뢰도 부족, 판별 불가)
        - G0_NotMold 예측 (60% 이상): G0 (곰팡이 아님 확신)
        - 나머지: 예측 라벨의 접두사 (G1~G4)
        """
        if confidence < CONFIDENCE_THRESHOLD:
            return "UNCLASSIFIED"
        if mold_name == "G0_NotMold":
            return "G0"
        return mold_name.split("_")[0]  # "G1_Stachybotrys" → "G1"

    def _check_multi_mold(self, all_probabilities: dict) -> dict | None:
        """
        복합 곰팡이 감지: G1~G4 확률 합이 60% 이상이고, 15% 이상인 곰팡이가 2개 이상이면 복합 곰팡이
        반환: {"detected_molds": [...], "total_confidence": float, "display_name": str} 또는 None
        """
        mold_classes = ["G1_Stachybotrys", "G2_Penicillium", "G3_WhiteMold", "G4_Serratia"]

        mold_probs = {cls: all_probabilities.get(cls, 0.0) for cls in mold_classes}
        mold_sum = sum(mold_probs.values())

        if mold_sum < MULTI_MOLD_SUM_THRESHOLD:
            return None

        # 15% 이상인 곰팡이만 유의미하게 필터링
        significant = [
            {
                "grade": cls.split("_")[0],
                "name": MOLD_KOREAN_NAMES[cls.split("_")[0]],
                "confidence": prob,
                "class_name": cls
            }
            for cls, prob in mold_probs.items()
            if prob >= MULTI_MOLD_INDIVIDUAL_THRESHOLD
        ]

        # 유의미한 곰팡이가 2개 미만이면 복합이 아님
        if len(significant) < 2:
            return None

        # 신뢰도 내림차순 정렬
        significant.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "detected_molds": significant,
            "total_confidence": round(mold_sum, 1),
            "display_name": " + ".join(
                f"{m['grade']}({m['name']})" for m in significant
            )
        }

    async def _handle_g3_white_mold(self, mold_name: str, probability: float) -> str:
        """
        G3(흰곰팡이 + 백화현상) 특별 처리
        RAG JSON 응답의 insight 필드에 물 테스트 안내를 통합하여 반환
        """
        rag_result = await search_service.get_mold_solution_with_rag(mold_name, probability)
        rag_json_str = rag_result["rag_solution"]

        water_test_guide = (
            "\n\n[추가 진단 안내] 하얀 오염물이 판단되었습니다.\n"
            "이 오염물이 콘크리트 또는 벽돌 위에 있다면 간단한 테스트를 해보세요:\n"
            "→ 물을 약간 뿌려보세요.\n"
            "  • 물에 바로 녹으면 → 백화현상(소금기). 벽돌·콘크리트 내부의 수분이 건조할 때 표면으로 올라온 것입니다.\n"
            "  • 물이 맺혀서 바로 사라지지 않으면 → 곰팡이. 환기 및 제곰팡이 처리가 필요합니다."
        )

        try:
            rag_data = json.loads(rag_json_str)
            # insight 필드에 물 테스트 안내 추가 (JSON 구조 유지)
            rag_data["insight"] = rag_data.get("insight", "") + water_test_guide
            return json.dumps(rag_data, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # JSON 파싱 실패 시 문자열로 추가 (fallback)
            return rag_json_str + water_test_guide
