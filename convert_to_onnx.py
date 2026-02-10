# convert_to_onnx.py
# 1회성 변환 스크립트: .pth → dual-output .onnx (logits + feature maps)
# 로컬 환경에서만 실행 (서버 배포에는 포함하지 않음)
# 실행: python convert_to_onnx.py

import torch
import torch.nn as nn
import timm
import onnx
import onnx.numpy_helper
import numpy as np
import os

# ── 경로 설정 ──
PTH_PATH = os.path.join("app", "domains", "diagnosis", "models", "efficientnet_b0_mold.pt")
ONNX_PATH = os.path.join("app", "domains", "diagnosis", "models", "efficientnet_b0_mold.onnx")
NUM_CLASSES = 5


class EfficientNetDualOutput(nn.Module):
    """
    timm EfficientNet-B0를 감싸서 2개 출력을 반환하는 wrapper
    - output 1: logits (1, NUM_CLASSES) — 분류 결과
    - output 2: features (1, 1280, 7, 7) — 마지막 conv layer feature map (CAM용)
    """
    def __init__(self, base_model):
        super().__init__()
        self.base_model = base_model

    def forward(self, x):
        # timm EfficientNet: forward_features()로 feature map 추출
        feature_maps = self.base_model.forward_features(x)  # (1, 1280, 7, 7)

        # global average pooling + classifier
        pooled = self.base_model.global_pool(feature_maps)  # (1, 1280)
        logits = self.base_model.classifier(pooled)          # (1, NUM_CLASSES)

        return logits, feature_maps


def step1_convert_pth_to_onnx():
    """Step 1: PyTorch .pth → dual-output ONNX .onnx 변환"""
    print("=" * 50)
    print("[Step 1] PyTorch → Dual-Output ONNX 변환")
    print("=" * 50)

    # 모델 로드 (체크포인트 형식 자동 감지)
    checkpoint = torch.load(PTH_PATH, map_location="cpu")

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        # 체크포인트 형식: {epoch, model_state_dict, optimizer_state_dict, ...}
        state_dict = checkpoint["model_state_dict"]
        print(f"  체크포인트 형식 감지 (epoch: {checkpoint.get('epoch')}, val_acc: {checkpoint.get('val_acc')})")
        print(f"  class_names: {checkpoint.get('class_names')}")

        # 키 접두사 자동 제거 (예: "model.features.0.0.weight" → "features.0.0.weight")
        first_key = list(state_dict.keys())[0]
        if first_key.startswith("model."):
            print(f"  키 접두사 'model.' 감지 → 제거 중...")
            state_dict = {k.replace("model.", "", 1): v for k, v in state_dict.items()}

        base_model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=NUM_CLASSES)
        base_model.load_state_dict(state_dict)
    elif isinstance(checkpoint, dict):
        # 순수 state_dict 형식
        base_model = timm.create_model('efficientnet_b0', pretrained=False, num_classes=NUM_CLASSES)
        base_model.load_state_dict(checkpoint)
    else:
        # 모델 전체 저장 형식
        base_model = checkpoint

    base_model.eval()

    # Dual-output wrapper로 감싸기
    model = EfficientNetDualOutput(base_model)
    model.eval()

    # feature map shape 확인
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        logits, features = model(dummy_input)
        print(f"  Logits shape: {logits.shape}")       # (1, 4)
        print(f"  Features shape: {features.shape}")   # (1, 1280, 7, 7)

    # ONNX export (레거시 exporter 강제 사용)
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_PATH,
        export_params=True,
        opset_version=13,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output", "features"],  # dual output
        dynamo=False,
    )

    # 유효성 검증
    onnx_model = onnx.load(ONNX_PATH)
    onnx.checker.check_model(onnx_model)

    onnx_size = os.path.getsize(ONNX_PATH) / (1024 * 1024)
    print(f"  ONNX 모델 저장: {ONNX_PATH} ({onnx_size:.1f}MB)")
    print(f"  유효성 검증 통과")

    return base_model


def step2_verify_dual_output():
    """Step 2: dual-output ONNX 모델 검증"""
    print()
    print("=" * 50)
    print("[Step 2] Dual-Output 검증")
    print("=" * 50)

    import onnxruntime as ort

    # 출력 노드 확인
    onnx_model = onnx.load(ONNX_PATH)
    output_names = [out.name for out in onnx_model.graph.output]
    print(f"  출력 노드: {output_names}")

    # FC weight 존재 확인
    fc_weight_found = False
    for initializer in onnx_model.graph.initializer:
        if "classifier" in initializer.name and "weight" in initializer.name:
            weights = onnx.numpy_helper.to_array(initializer)
            print(f"  FC Weight 발견: {initializer.name}, shape={weights.shape}")
            fc_weight_found = True
            break

    if not fc_weight_found:
        print("  경고: FC Weight를 찾지 못했습니다!")

    # ONNX Runtime으로 추론 테스트
    session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    dummy_np = np.random.randn(1, 3, 224, 224).astype(np.float32)

    outputs = session.run(None, {"input": dummy_np})
    print(f"  Output[0] (logits) shape: {outputs[0].shape}")     # (1, 4)
    print(f"  Output[1] (features) shape: {outputs[1].shape}")   # (1, 1280, 7, 7)

    assert outputs[0].shape == (1, NUM_CLASSES), f"Logits shape 불일치: {outputs[0].shape}"
    assert outputs[1].shape == (1, 1280, 7, 7), f"Features shape 불일치: {outputs[1].shape}"
    print(f"  검증 통과!")


def step3_verify_output_consistency(pytorch_model):
    """Step 3: PyTorch vs ONNX 출력 일치 검증"""
    print()
    print("=" * 50)
    print("[Step 3] PyTorch vs ONNX 출력 비교")
    print("=" * 50)

    import onnxruntime as ort

    dummy = torch.randn(1, 3, 224, 224)

    # PyTorch 추론
    pytorch_model.eval()
    with torch.no_grad():
        pytorch_logits = pytorch_model(dummy).numpy()
    pytorch_exp = np.exp(pytorch_logits - np.max(pytorch_logits, axis=1, keepdims=True))
    pytorch_probs = pytorch_exp / pytorch_exp.sum(axis=1, keepdims=True)

    # ONNX 추론
    session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    onnx_outputs = session.run(None, {"input": dummy.numpy()})
    onnx_logits = onnx_outputs[0]
    onnx_exp = np.exp(onnx_logits - np.max(onnx_logits, axis=1, keepdims=True))
    onnx_probs = onnx_exp / onnx_exp.sum(axis=1, keepdims=True)

    max_diff = float(np.abs(pytorch_probs - onnx_probs).max())
    same_class = int(np.argmax(pytorch_probs)) == int(np.argmax(onnx_probs))

    print(f"  PyTorch 확률: {pytorch_probs[0]}")
    print(f"  ONNX    확률: {onnx_probs[0]}")
    print(f"  최대 차이:    {max_diff:.6f}")
    print(f"  동일 클래스:  {same_class}")

    if max_diff < 0.01:
        print(f"  검증 통과: 출력이 매우 유사합니다.")
    else:
        print(f"  경고: 출력 차이가 있습니다 ({max_diff:.4f}).")


def step4_cam_test():
    """Step 4: Weight-based CAM 테스트"""
    print()
    print("=" * 50)
    print("[Step 4] Weight-based CAM 테스트")
    print("=" * 50)

    import onnxruntime as ort
    from PIL import Image

    # FC weight 추출
    onnx_model = onnx.load(ONNX_PATH)
    fc_weights = None
    for initializer in onnx_model.graph.initializer:
        if "classifier" in initializer.name and "weight" in initializer.name:
            fc_weights = onnx.numpy_helper.to_array(initializer)
            break

    if fc_weights is None:
        print("  FC Weight를 찾지 못했습니다. CAM 테스트 건너뜀.")
        return

    # 더미 이미지로 추론
    session = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])
    dummy_np = np.random.randn(1, 3, 224, 224).astype(np.float32)
    outputs = session.run(None, {"input": dummy_np})

    logits = outputs[0][0]
    features = outputs[1][0]  # (1280, 7, 7)

    # softmax
    exp_logits = np.exp(logits - np.max(logits))
    probs = exp_logits / exp_logits.sum()
    predicted_idx = int(np.argmax(probs))

    # CAM 계산
    weights = fc_weights[predicted_idx]  # (1280,)
    cam = np.zeros(features.shape[1:], dtype=np.float32)  # (7, 7)
    for i in range(features.shape[0]):
        cam += weights[i] * features[i]

    cam = np.maximum(cam, 0)  # ReLU
    if cam.max() > 0:
        cam = (cam - cam.min()) / (cam.max() - cam.min())

    # 224x224로 resize
    cam_pil = Image.fromarray((cam * 255).astype(np.uint8), mode='L')
    cam_resized = cam_pil.resize((224, 224), Image.BILINEAR)
    cam_final = np.array(cam_resized, dtype=np.float32) / 255.0

    # bbox 추출
    binary_mask = (cam_final > 0.5).astype(np.uint8)
    rows = np.any(binary_mask, axis=1)
    cols = np.any(binary_mask, axis=0)

    if rows.any() and cols.any():
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        print(f"  예측 클래스: {predicted_idx} (confidence: {probs[predicted_idx]*100:.1f}%)")
        print(f"  CAM heatmap shape: {cam_final.shape}")
        print(f"  Bbox: x_min={x_min}, y_min={y_min}, x_max={x_max}, y_max={y_max}")
    else:
        print(f"  threshold 0.5 초과 영역 없음 (더미 이미지이므로 정상)")

    print(f"  CAM 테스트 완료!")


if __name__ == "__main__":
    print(f"원본 .pth 파일: {PTH_PATH} (존재: {os.path.exists(PTH_PATH)})")
    print()

    pytorch_model = step1_convert_pth_to_onnx()
    step2_verify_dual_output()
    step3_verify_output_consistency(pytorch_model)
    step4_cam_test()

    print()
    print("=" * 50)
    print("변환 완료!")
    print(f"서버에 배포할 파일: {ONNX_PATH}")
    print("(dual-output: logits + feature maps)")
    print("=" * 50)
