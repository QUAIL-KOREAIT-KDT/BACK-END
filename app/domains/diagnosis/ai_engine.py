# BACK-END/app/domains/diagnosis/ai_engine.py

import torch
import torchvision.transforms as transforms
import torchvision.models as models
from PIL import Image

# 학습된 모델의 출력 클래스 라벨 (4개 분류)
# G3은 흰곰팡이(Mucor 등)와 백화현상(Efflorescence)을 병합
MOLD_CLASSES = [
    "G1_Stachybotrys",      # G1 검은곰팡이
    "G2_Penicillium",       # G2 녹색곰팡이
    "G3_WhiteMold",         # G3 흰곰팡이 + 백화현상 (병합)
    "G4_Serratia"           # G4 주황/분홍곰팡이
]

class EfficientNetEngine:
    def __init__(self, weights_path: str | None = None):
        self.device = torch.device("cpu")  # t3a.medium = CPU Only
        self.model = self._load_model(weights_path)
        self.model.eval()  # 추론 모드로 설정
        self.transform = self._get_transform()

    def _load_model(self, weights_path: str | None):
        model = models.efficientnet_b0(weights=None)
        # 마지막 FC 레이어를 4개 분류 클래스로 교체
        model.classifier[1] = torch.nn.Linear(
            model.classifier[1].in_features,
            len(MOLD_CLASSES)  # 4
        )
        # fine-tuning된 학습 가중치 로드
        if weights_path:
            state_dict = torch.load(weights_path, map_location=self.device)
            model.load_state_dict(state_dict)
        return model.to(self.device)

    def _get_transform(self):
        # EfficientNet-B0 공식 입력 크기: 224x224, ImageNet 정규화
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet mean
                std=[0.229, 0.224, 0.225]    # ImageNet std
            )
        ])

    def preprocess(self, image_file) -> torch.Tensor:
        """SpooledTemporaryFile → 정규화된 텐서 변환"""
        image = Image.open(image_file).convert("RGB")
        return self.transform(image).unsqueeze(0).to(self.device)  # batch dim 추가

    def predict(self, image_file) -> dict:
        """
        이미지 분류 추론 실행 (순수 모델 추론만 수행)
        반환: {"class_name": str, "confidence": float}
        임계치 체크, G3 특별 처리 등의 비즈니스 로직은 service.py에서 처리
        """
        input_tensor = self.preprocess(image_file)
        with torch.no_grad():
            logits = self.model(input_tensor)
            probabilities = torch.softmax(logits, dim=1)
            confidence, predicted_idx = torch.max(probabilities, dim=1)

        return {
            "class_name": MOLD_CLASSES[predicted_idx.item()],
            "confidence": round(confidence.item() * 100, 1)  # 퍼센트로 변환
        }
