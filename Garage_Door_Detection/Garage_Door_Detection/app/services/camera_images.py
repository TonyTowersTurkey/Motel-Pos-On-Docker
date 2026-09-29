import cv2
import numpy as np

CAMERA_IMAGE_WIDTH = 1920
CAMERA_IMAGE_HEIGHT = 1080


def normalize_camera_image(content: bytes) -> bytes:
    """Return a 1920x1080 JPEG without changing the source aspect ratio."""
    encoded = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded camera image could not be decoded")

    source_height, source_width = image.shape[:2]
    if source_width == CAMERA_IMAGE_WIDTH and source_height == CAMERA_IMAGE_HEIGHT:
        resized = image
    else:
        scale = min(CAMERA_IMAGE_WIDTH / source_width, CAMERA_IMAGE_HEIGHT / source_height)
        width = max(1, round(source_width * scale))
        height = max(1, round(source_height * scale))
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        fitted = cv2.resize(image, (width, height), interpolation=interpolation)
        resized = np.zeros((CAMERA_IMAGE_HEIGHT, CAMERA_IMAGE_WIDTH, 3), dtype=np.uint8)
        x = (CAMERA_IMAGE_WIDTH - width) // 2
        y = (CAMERA_IMAGE_HEIGHT - height) // 2
        resized[y : y + height, x : x + width] = fitted

    success, jpeg = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success:
        raise ValueError("The camera image could not be converted to JPEG")
    return jpeg.tobytes()
