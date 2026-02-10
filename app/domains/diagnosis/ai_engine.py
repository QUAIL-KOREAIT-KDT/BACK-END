# BACK-END/app/domains/diagnosis/ai_engine.py

import numpy as np
import onnxruntime as ort
from PIL import Image

# 학습된 모델의 출력 클래스 라벨 (4개 분류)
# G3은 흰곰팡이(Mucor 등)와 백화현상(Efflorescence)을 병합
MOLD_CLASSES = [
    "G0_NotMold",           # G0 곰팡이 아님
    "G1_Stachybotrys",      # G1 검은곰팡이
    "G2_Penicillium",       # G2 녹색곰팡이
    "G3_WhiteMold",         # G3 흰곰팡이 + 백화현상 (병합)
    "G4_Serratia"           # G4 주황/분홍곰팡이
]

# ImageNet 정규화 상수
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# CAM 바운딩박스 추출 임계값
CAM_THRESHOLD = 0.5


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

        # FC layer weight 추출 (서버 시작 시 1회, CAM 계산용)
        self.fc_weights = self._extract_fc_weights(weights_path)

    def _extract_fc_weights(self, onnx_path: str) -> np.ndarray:
        """ONNX initializer에서 classifier FC weight 추출 (shape: NUM_CLASSES × 1280)"""
        import onnx
        import onnx.numpy_helper

        model = onnx.load(onnx_path)
        for initializer in model.graph.initializer:
            if "classifier" in initializer.name and "weight" in initializer.name:
                return onnx.numpy_helper.to_array(initializer)

        raise ValueError("Classifier FC weight not found in ONNX model")

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
        이미지 분류 추론 (CAM 없이, 기존 호환성 유지)
        반환: {"class_name": str, "confidence": float}
        """
        result = self.predict_with_cam(image_file, generate_cam=False)
        return {
            "class_name": result["class_name"],
            "confidence": result["confidence"]
        }

    def predict_with_cam(self, image_file, generate_cam: bool = True) -> dict:
        """
        이미지 분류 추론 + Weight-based CAM 생성
        반환: {
            "class_name": str,
            "confidence": float,
            "cam_heatmap": np.ndarray(224,224) or None,
            "bbox": [x_min, y_min, x_max, y_max] or None
        }
        """
        input_data = self.preprocess(image_file)

        # ONNX 추론 (dual-output: logits + feature maps)
        outputs = self.session.run(None, {self.input_name: input_data})
        logits = outputs[0][0]      # shape: (4,)
        features = outputs[1][0]    # shape: (1280, 7, 7)

        # softmax
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / exp_logits.sum()

        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx])

        result = {
            "class_name": MOLD_CLASSES[predicted_idx],
            "confidence": round(confidence * 100, 1),
            "cam_heatmap": None,
            "bbox": None
        }

        if generate_cam:
            cam_heatmap = self._compute_cam(features, predicted_idx)
            bbox = self._extract_bbox(cam_heatmap)
            result["cam_heatmap"] = cam_heatmap
            result["bbox"] = bbox

        return result

    def _compute_cam(self, features: np.ndarray, class_idx: int) -> np.ndarray:
        """
        Weight-based CAM 계산
        features: (1280, 7, 7), class_idx: 예측된 클래스 인덱스
        반환: (224, 224) normalized heatmap [0, 1]
        """
        weights = self.fc_weights[class_idx]  # (1280,)

        # Weighted sum: 벡터화 연산으로 빠르게 계산
        cam = np.einsum('i,ijk->jk', weights, features)  # (7, 7)

        # ReLU
        cam = np.maximum(cam, 0)

        # Normalize to [0, 1]
        cam_max = cam.max()
        if cam_max > 0:
            cam = (cam - cam.min()) / (cam_max - cam.min())

        # 7x7 → 224x224 resize (PIL bilinear)
        cam_pil = Image.fromarray((cam * 255).astype(np.uint8), mode='L')
        cam_resized = cam_pil.resize((224, 224), Image.BILINEAR)

        return np.array(cam_resized, dtype=np.float32) / 255.0

    def _extract_bbox(self, cam_heatmap: np.ndarray) -> list[int]:
        """
        CAM heatmap에서 바운딩박스 추출
        cam_heatmap: (224, 224) [0, 1]
        반환: [x_min, y_min, x_max, y_max]
        """
        binary_mask = (cam_heatmap > CAM_THRESHOLD).astype(np.uint8)

        rows = np.any(binary_mask, axis=1)
        cols = np.any(binary_mask, axis=0)

        if not rows.any() or not cols.any():
            return [0, 0, 224, 224]

        y_min, y_max = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
        x_min, x_max = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])

        # 10% padding
        pad_y = max(1, int((y_max - y_min) * 0.1))
        pad_x = max(1, int((x_max - x_min) * 0.1))

        y_min = max(0, y_min - pad_y)
        y_max = min(223, y_max + pad_y)
        x_min = max(0, x_min - pad_x)
        x_max = min(223, x_max + pad_x)

        return [x_min, y_min, x_max, y_max]
