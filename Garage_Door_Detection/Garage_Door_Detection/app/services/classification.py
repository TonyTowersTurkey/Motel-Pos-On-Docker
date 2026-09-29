import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.core.config import settings
from app.models import DoorState


class ClassificationModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClassificationPrediction:
    state: DoorState
    confidence: float
    closed_probability: float
    open_probability: float


class YoloGarageDoorClassifier:
    """Load one Ultralytics classification model and reuse it for every batch."""

    def __init__(self, model_path: Path, confidence_threshold: float) -> None:
        if not model_path.is_file():
            raise ClassificationModelError(f"Classification model not found: {model_path}")
        if not 0 <= confidence_threshold <= 1:
            raise ClassificationModelError("Classification confidence threshold must be 0-1")

        settings.classification_cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(
            "MPLCONFIGDIR", str(settings.classification_cache_dir.resolve())
        )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ClassificationModelError(
                "Ultralytics is not installed; install the project dependencies"
            ) from exc

        try:
            self._model = YOLO(str(model_path))
        except Exception as exc:
            raise ClassificationModelError(f"Could not load {model_path}: {exc}") from exc

        names = self._model.names
        if isinstance(names, list):
            names = dict(enumerate(names))
        self._class_indexes = {
            str(name).strip().lower(): int(index) for index, name in names.items()
        }
        if set(self._class_indexes) != {"open", "closed"}:
            raise ClassificationModelError(
                "Classification model classes must be exactly 'open' and 'closed'; "
                f"found {sorted(self._class_indexes)}"
            )

        self.confidence_threshold = confidence_threshold
        self.model_version = f"{model_path.name}:{_file_hash(model_path)[:12]}"

    def predict(self, image_paths: list[Path]) -> list[ClassificationPrediction]:
        if not image_paths:
            return []
        try:
            results = self._model.predict(
                source=[str(path) for path in image_paths],
                verbose=False,
            )
        except Exception as exc:
            raise ClassificationModelError(f"Classification failed: {exc}") from exc

        predictions: list[ClassificationPrediction] = []
        for result in results:
            if result.probs is None:
                raise ClassificationModelError("Model did not return classification probabilities")
            probabilities = result.probs.data.tolist()
            closed_probability = float(probabilities[self._class_indexes["closed"]])
            open_probability = float(probabilities[self._class_indexes["open"]])
            if open_probability >= closed_probability:
                candidate = DoorState.open
                confidence = open_probability
            else:
                candidate = DoorState.closed
                confidence = closed_probability
            state = (
                candidate
                if confidence >= self.confidence_threshold
                else DoorState.unknown
            )
            predictions.append(
                ClassificationPrediction(
                    state=state,
                    confidence=confidence,
                    closed_probability=closed_probability,
                    open_probability=open_probability,
                )
            )

        if len(predictions) != len(image_paths):
            raise ClassificationModelError(
                f"Model returned {len(predictions)} results for {len(image_paths)} images"
            )
        return predictions


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
