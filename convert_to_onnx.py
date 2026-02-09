# convert_to_onnx.py
# 1회성 변환 스크립트: .pth → .onnx → quantized .onnx
# 로컬 환경에서만 실행 (서버 배포에는 포함하지 않음)
# 실행: python convert_to_onnx.py

import torch
import torchvision.models as models
import onnx
import numpy as np
import os

# ── 경로 설정 ──
PTH_PATH = os.path.join("app", "domains", "diagnosis", "models", "efficientnet_b0_mold.pth")
ONNX_PATH = os.path.join("app", "domains", "diagnosis", "models", "efficientnet_b0_mold.onnx")
QUANTIZED_PATH = os.path.join("app", "domains", "diagnosis", "models", "efficientnet_b0_mold_quantized.onnx")
NUM_CLASSES = 4


def step1_convert_pth_to_onnx():
    """Step 1: PyTorch .pth → ONNX .onnx 변환"""
    print("=" * 50)
    print("[Step 1] PyTorch → ONNX 변환")
    print("=" * 50)

    # 모델 구조 생성 및 가중치 로드
    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, NUM_CLASSES)
    state_dict = torch.load(PTH_PATH, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()

    # ONNX export (레거시 exporter 강제 사용)
    dummy_input = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_PATH,
        export_params=True,
        opset_version=13,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamo=False,  # 레거시 exporter 강제 (dynamo 비활성화)
    )

    # 유효성 검증
    onnx_model = onnx.load(ONNX_PATH)
    onnx.checker.check_model(onnx_model)

    onnx_size = os.path.getsize(ONNX_PATH) / (1024 * 1024)
    print(f"  ONNX 모델 저장: {ONNX_PATH} ({onnx_size:.1f}MB)")
    print(f"  유효성 검증 통과")
    return model


def step2_quantize_onnx():
    """Step 2: ONNX 동적 양자화 (FP32 → INT8)"""
    print()
    print("=" * 50)
    print("[Step 2] ONNX 동적 양자화 (INT8)")
    print("=" * 50)

    from onnxruntime.quantization import quantize_dynamic, QuantType

    # 양자화 전에 shape inference 전처리 (필수)
    preprocessed_path = ONNX_PATH.replace(".onnx", "_preprocessed.onnx")
    onnx.shape_inference.infer_shapes_path(ONNX_PATH, preprocessed_path)
    print(f"  Shape inference 전처리 완료")

    quantize_dynamic(
        model_input=preprocessed_path,
        model_output=QUANTIZED_PATH,
        weight_type=QuantType.QUInt8
    )

    # 전처리 임시 파일 삭제
    if os.path.exists(preprocessed_path):
        os.remove(preprocessed_path)

    original_size = os.path.getsize(ONNX_PATH) / (1024 * 1024)
    quantized_size = os.path.getsize(QUANTIZED_PATH) / (1024 * 1024)
    reduction = (1 - quantized_size / original_size) * 100

    print(f"  원본 ONNX:   {original_size:.1f}MB")
    print(f"  양자화 ONNX: {quantized_size:.1f}MB")
    print(f"  크기 감소:   {reduction:.1f}%")


def step3_verify(pytorch_model):
    """Step 3: 원본(PyTorch) vs 양자화(ONNX) 출력 비교 검증"""
    print()
    print("=" * 50)
    print("[Step 3] 출력 비교 검증")
    print("=" * 50)

    import onnxruntime as ort

    dummy = torch.randn(1, 3, 224, 224)

    # PyTorch 원본 추론
    with torch.no_grad():
        pytorch_logits = pytorch_model(dummy).numpy()
    pytorch_exp = np.exp(pytorch_logits - np.max(pytorch_logits, axis=1, keepdims=True))
    pytorch_probs = pytorch_exp / pytorch_exp.sum(axis=1, keepdims=True)

    # ONNX 양자화 모델 추론
    session = ort.InferenceSession(QUANTIZED_PATH, providers=["CPUExecutionProvider"])
    onnx_logits = session.run(None, {"input": dummy.numpy()})[0]
    onnx_exp = np.exp(onnx_logits - np.max(onnx_logits, axis=1, keepdims=True))
    onnx_probs = onnx_exp / onnx_exp.sum(axis=1, keepdims=True)

    # 비교
    max_diff = float(np.abs(pytorch_probs - onnx_probs).max())
    same_class = int(np.argmax(pytorch_probs)) == int(np.argmax(onnx_probs))

    print(f"  PyTorch 확률: {pytorch_probs[0]}")
    print(f"  ONNX    확률: {onnx_probs[0]}")
    print(f"  최대 차이:    {max_diff:.6f}")
    print(f"  동일 클래스:  {same_class}")

    if max_diff < 0.05:
        print(f"  검증 통과: 양자화 모델 출력이 원본과 충분히 유사합니다.")
    else:
        print(f"  경고: 출력 차이가 큽니다 ({max_diff:.4f}). 양자화 없이 ONNX만 사용하는 것을 권장합니다.")


def step4_benchmark():
    """Step 4: 추론 속도 벤치마크"""
    print()
    print("=" * 50)
    print("[Step 4] 추론 속도 벤치마크")
    print("=" * 50)

    import time
    import onnxruntime as ort

    dummy_np = np.random.randn(1, 3, 224, 224).astype(np.float32)
    n_runs = 50

    # PyTorch 벤치마크
    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, NUM_CLASSES)
    model.load_state_dict(torch.load(PTH_PATH, map_location="cpu"))
    model.eval()

    dummy_tensor = torch.from_numpy(dummy_np)
    # warmup
    for _ in range(5):
        with torch.no_grad():
            model(dummy_tensor)

    start = time.perf_counter()
    for _ in range(n_runs):
        with torch.no_grad():
            model(dummy_tensor)
    pytorch_time = (time.perf_counter() - start) / n_runs * 1000

    # ONNX 양자화 벤치마크
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.intra_op_num_threads = 2
    session = ort.InferenceSession(QUANTIZED_PATH, sess_options, providers=["CPUExecutionProvider"])

    # warmup
    for _ in range(5):
        session.run(None, {"input": dummy_np})

    start = time.perf_counter()
    for _ in range(n_runs):
        session.run(None, {"input": dummy_np})
    onnx_time = (time.perf_counter() - start) / n_runs * 1000

    speedup = (1 - onnx_time / pytorch_time) * 100

    print(f"  PyTorch FP32:       {pytorch_time:.1f}ms")
    print(f"  ONNX Quantized:     {onnx_time:.1f}ms")
    print(f"  속도 개선:          {speedup:.1f}%")


if __name__ == "__main__":
    print(f"원본 .pth 파일: {PTH_PATH} (존재: {os.path.exists(PTH_PATH)})")
    print()

    pytorch_model = step1_convert_pth_to_onnx()
    step2_quantize_onnx()
    step3_verify(pytorch_model)
    step4_benchmark()

    print()
    print("=" * 50)
    print("변환 완료!")
    print(f"서버에 배포할 파일: {QUANTIZED_PATH}")
    print("=" * 50)
