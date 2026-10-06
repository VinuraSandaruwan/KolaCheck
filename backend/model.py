"""Load and run the packaged KolaCheck TFLite model."""
from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path
import threading
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from ai_edge_litert.interpreter import Interpreter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "app" / "assets" / "model.tflite"
DEFAULT_LABELS_PATH = PROJECT_ROOT / "app" / "assets" / "labels.txt"
IMAGE_SIZE = 224
MAX_IMAGE_PIXELS = 25_000_000
EXPECTED_LABELS = {
    "algal_leaf_spot", "black_blight", "blister_blight",
    "gray_blight", "healthy", "spider_mite",
}


class InvalidImageError(ValueError):
    """Raised when an uploaded file is not a safe, supported image."""


class ModelRuntimeError(RuntimeError):
    """Raised when the packaged model cannot accept or produce valid tensors."""


def _resize_bilinear_float(image: np.ndarray, size: int) -> np.ndarray:
    """Match tf.image.resize(..., method='bilinear', antialias=False).

    Keep interpolated pixel values as float32. Pillow's resize returns 8-bit
    pixels, which changes the model input and measurably changes evaluation.
    """
    height, width, _ = image.shape
    y = np.clip((np.arange(size, dtype=np.float32) + 0.5) * (height / size) - 0.5, 0, height - 1)
    x = np.clip((np.arange(size, dtype=np.float32) + 0.5) * (width / size) - 0.5, 0, width - 1)
    y0 = np.floor(y).astype(np.intp)
    x0 = np.floor(x).astype(np.intp)
    y1 = np.minimum(y0 + 1, height - 1)
    x1 = np.minimum(x0 + 1, width - 1)
    wy = (y - y0).reshape(size, 1, 1)
    wx = (x - x0).reshape(1, size, 1)
    source = image.astype(np.float32, copy=False)
    top = source[:, x0, :] * (1.0 - wx) + source[:, x1, :] * wx
    bottom = source[:, x0, :] * (1.0 - wx) + source[:, x1, :] * wx
    resized = top[y0, :, :] * (1.0 - wy) + bottom[y1, :, :] * wy
    return resized[None, ...]


class TeaLeafPredictor:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH, labels_path: Path = DEFAULT_LABELS_PATH):
        if not model_path.is_file() or not labels_path.is_file():
            raise FileNotFoundError("Model or labels file is missing from app/assets")

        self.labels = [line.strip() for line in labels_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if set(self.labels) != EXPECTED_LABELS or len(self.labels) != len(EXPECTED_LABELS):
            raise ModelRuntimeError("Model labels must contain the six unique KolaCheck classes")

        model_bytes = model_path.read_bytes()
        self.model_version = hashlib.sha256(model_bytes).hexdigest()[:16]
        self._interpreter = Interpreter(model_content=model_bytes, num_threads=2)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._output = self._interpreter.get_output_details()[0]
        if self._input["shape"].tolist() != [1, IMAGE_SIZE, IMAGE_SIZE, 3]:
            raise ModelRuntimeError(f"Unexpected model input shape: {self._input['shape']}")
        if self._output["shape"].tolist() != [1, len(self.labels)]:
            raise ModelRuntimeError(f"Unexpected model output shape: {self._output['shape']}")
        self._lock = threading.Lock()

    def _decode(self, image_bytes: bytes) -> np.ndarray:
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InvalidImageError("Use a JPEG, PNG, or WebP image")
                if source.width < 32 or source.height < 32:
                    raise InvalidImageError("Image dimensions must be at least 32 x 32 pixels")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError("Image is too large; maximum supported size is 25 megapixels")
                image = ImageOps.exif_transpose(source).convert("RGB")
                return _resize_bilinear_float(np.asarray(image, dtype=np.uint8), IMAGE_SIZE)
        except InvalidImageError:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise InvalidImageError("The uploaded file is not a valid supported image") from exc

    @staticmethod
    def _quantize(values: np.ndarray, detail: dict[str, Any]) -> np.ndarray:
        dtype = detail["dtype"]
        if np.issubdtype(dtype, np.integer):
            scale, zero_point = detail["quantization"]
            if not scale:
                raise ModelRuntimeError("Integer model input is missing quantization parameters")
            values = np.round(values / scale + zero_point)
            values = np.clip(values, np.iinfo(dtype).min, np.iinfo(dtype).max)
        return values.astype(dtype)

    def predict(self, image_bytes: bytes) -> dict[str, Any]:
        tensor = self._quantize(self._decode(image_bytes), self._input)
        with self._lock:
            self._interpreter.set_tensor(self._input["index"], tensor)
            self._interpreter.invoke()
            scores = self._interpreter.get_tensor(self._output["index"])[0]

        if np.issubdtype(scores.dtype, np.integer):
            scale, zero_point = self._output["quantization"]
            scores = (scores.astype(np.float32) - zero_point) * scale
        scores = np.asarray(scores, dtype=np.float32)
        if scores.shape != (len(self.labels),) or not np.isfinite(scores).all():
            raise ModelRuntimeError("Model returned invalid prediction scores")
        if np.any(scores < -1e-5) or np.any(scores > 1.00001):
            raise ModelRuntimeError("Model output is outside the expected probability range")

        order = np.argsort(scores)[::-1]
        top_index = int(order[0])
        confidence = float(scores[top_index])
        return {
            "label": self.labels[top_index],
            "confidence": confidence,
            "needs_review": confidence < 0.60,
            "top_predictions": [
                {"label": self.labels[int(index)], "confidence": float(scores[index])}
                for index in order[:3]
            ],
            "model_version": self.model_version,
        }
