import cv2
import numpy as np

from app.services.camera_images import normalize_camera_image


def test_normalize_camera_image_letterboxes_to_1920x1080() -> None:
    source = np.full((800, 600, 3), 255, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", source)
    assert success

    normalized = normalize_camera_image(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(normalized, dtype=np.uint8), cv2.IMREAD_COLOR)

    assert decoded.shape[:2] == (1080, 1920)
    assert decoded[540, 960].mean() > 245
    assert decoded[540, 100].mean() < 10
