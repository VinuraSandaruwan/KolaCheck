r"""Evaluate the packaged TFLite model on the untouched original-image test split.

Run from training/: python evaluate_tflite.py ..\data
This uses the same backend predictor and image preprocessing as the inference API.
"""
import csv
import json
import pathlib
import sys

import numpy as np

PROJECT = pathlib.Path(__file__).resolve().parents[1]
DATA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "../data").resolve()
METADATA = PROJECT / "data-source" / "Sri Lankan Tea Leaf Dataset" / "metadata files"
LABELS_PATH = PROJECT / "app" / "assets" / "labels.txt"
METRICS_PATH = pathlib.Path(__file__).resolve().parent / "metrics.json"
sys.path.insert(0, str(PROJECT))
from backend.model import TeaLeafPredictor  # noqa: E402

labels = [line.strip() for line in LABELS_PATH.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
with (METADATA / "test_original_only_baseid_split.csv").open(newline="", encoding="utf-8-sig") as handle:
    test_rows = list(csv.DictReader(handle))
test_ids = {row["base_id"] for row in test_rows}
if len(test_ids) != len(test_rows):
    raise ValueError("Test split manifest contains duplicate base IDs")

condition_by_id = {}
with (METADATA / "SLTeaLeaf_metadata_raw.csv").open(newline="", encoding="utf-8-sig") as handle:
    for row in csv.DictReader(handle):
        condition_by_id[row["image_id"]] = row.get("acquisition_condition", "uncertain") or "uncertain"

image_paths = []
for class_name in labels:
    class_dir = DATA / class_name
    if not class_dir.is_dir():
        raise FileNotFoundError(f"Missing class directory: {class_dir}")
    for image_path in sorted(class_dir.iterdir()):
        if image_path.is_file() and image_path.suffix.lower() in {".jpg", ".jpeg"} and image_path.stem in test_ids:
            image_paths.append((image_path, class_name))
if len(image_paths) != len(test_ids):
    raise ValueError(f"Found {len(image_paths)} test files, expected {len(test_ids)}")

predictor = TeaLeafPredictor()
confusions = {"all": np.zeros((len(labels), len(labels)), dtype=np.int64)}
seen_ids = set()
for path, true_label in image_paths:
    if path.stem in seen_ids:
        raise ValueError(f"Duplicate image ID across class folders: {path.stem}")
    seen_ids.add(path.stem)
    condition = condition_by_id.get(path.stem, "uncertain")
    confusions.setdefault(condition, np.zeros((len(labels), len(labels)), dtype=np.int64))
    result = predictor.predict(path.read_bytes())
    true_index = labels.index(true_label)
    predicted_index = labels.index(result["label"])
    confusions["all"][true_index, predicted_index] += 1
    confusions[condition][true_index, predicted_index] += 1


def make_report(matrix):
    total = int(matrix.sum())
    report = {}
    for index, class_name in enumerate(labels):
        true_positive = int(matrix[index, index])
        support = int(matrix[index, :].sum())
        predicted = int(matrix[:, index].sum())
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[class_name] = {"precision": precision, "recall": recall, "f1-score": f1, "support": support}
    report["accuracy"] = float(np.trace(matrix) / total) if total else 0.0
    for average_name, weights in (
        ("macro avg", [1.0] * len(labels)),
        ("weighted avg", [report[name]["support"] for name in labels]),
    ):
        denominator = sum(weights)
        report[average_name] = {
            key: sum(report[name][key] * weight for name, weight in zip(labels, weights)) / denominator if denominator else 0.0
            for key in ("precision", "recall", "f1-score")
        }
        report[average_name]["support"] = total
    return report


with METRICS_PATH.open(encoding="utf-8-sig") as handle:
    metrics = json.load(handle)
if labels != metrics["classes"]:
    raise ValueError("app/assets/labels.txt does not match training metrics class order")
metrics["tflite_evaluation"] = {
    "evaluation_split": "test_original_only_baseid_split",
    "test_set_usage_note": (
        "This supplied test split has been used to compare model artifacts; "
        "use a new independent field-photo set for future final claims."
    ),
    "sample_count": len(image_paths),
    "model_version": predictor.model_version,
    "labels_match_app": True,
    "input_shape": [1, 224, 224, 3],
    "output_shape": [1, len(labels)],
    "preprocessing": "EXIF transpose, RGB, 224x224 bilinear resize; same code as backend inference",
    "report": make_report(confusions["all"]),
    "confusion_matrix": confusions["all"].tolist(),
    "acquisition_condition_reports": {
        condition: {
            "sample_count": int(matrix.sum()),
            "accuracy": make_report(matrix)["accuracy"],
            "report": make_report(matrix),
        }
        for condition, matrix in confusions.items() if condition != "all"
    },
}
METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print(json.dumps(metrics["tflite_evaluation"], indent=2))
