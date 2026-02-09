# BACK-END/app/domains/diagnosis/ai_engine.py

import numpy as np
import onnxruntime as ort
from PIL import Image

# 학습된 모델의 출력 클래스 라벨 (4개 분류)
# G3은 흰곰팡이(Mucor 등)와 백화현상(Efflorescence)을 병합
MOLD_CLASSES = [
    "G1_Stachybotrys",      # G1 검은곰팡이
    "G2_Penicillium",       # G2 녹색곰팡이
    "G3_WhiteMold",         # G3 흰곰팡이 + 백화현상 (병합)
    "G4_Serratia"           # G4 주황/분홍곰팡이
]

# ImageNet 정규화 상수
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class EfficientNetEngine:
    def __init__(self, weights_path: str | None = None):
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 2  # t3a.medium 2 vCPU

        self.session = ort.InferenceSession(
            weights_path,
            sess_options,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def preprocess(self, image_file) -> np.ndarray:
        """SpooledTemporaryFile/BytesIO → 정규화된 numpy 배열 변환"""
        image = Image.open(image_file).convert("RGB")
        image = image.resize((224, 224), Image.BILINEAR)

        # PIL Image → float32 배열 (0~1 범위)
        img_array = np.array(image, dtype=np.float32) / 255.0

        # ImageNet 정규화
        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

        # HWC → CHW → NCHW (배치 차원 추가)
        img_array = img_array.transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)

        return img_array

    def predict(self, image_file) -> dict:
        """
        이미지 분류 추론 실행 (순수 모델 추론만 수행)
        반환: {"class_name": str, "confidence": float}
        임계치 체크, G3 특별 처리 등의 비즈니스 로직은 service.py에서 처리
        """
        input_data = self.preprocess(image_file)

        # ONNX Runtime 추론
        outputs = self.session.run(None, {self.input_name: input_data})
        logits = outputs[0][0]  # shape: (4,)

        # softmax
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / exp_logits.sum()

        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx])

        return {
            "class_name": MOLD_CLASSES[predicted_idx],
            "confidence": round(confidence * 100, 1)  # 퍼센트로 변환
        }
