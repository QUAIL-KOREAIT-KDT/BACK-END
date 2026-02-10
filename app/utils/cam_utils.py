# BACK-END/app/utils/cam_utils.py

import io
import numpy as np
from PIL import Image, ImageDraw


def draw_bbox_on_image(image_bytes: bytes, bbox: list[int]) -> io.BytesIO:
    """
    원본 이미지에 빨간 바운딩박스를 그려 BytesIO로 반환

    Args:
        image_bytes: 원본 이미지의 bytes
        bbox: [x_min, y_min, x_max, y_max] (224x224 기준 좌표)

    Returns:
        BytesIO: 바운딩박스가 그려진 JPEG 이미지
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((224, 224), Image.BILINEAR)

    draw = ImageDraw.Draw(img)
    x_min, y_min, x_max, y_max = bbox
    draw.rectangle(
        [(x_min, y_min), (x_max, y_max)],
        outline=(255, 0, 0),
        width=3
    )

    output = io.BytesIO()
    img.save(output, format='JPEG', quality=95)
    output.seek(0)

    return output
