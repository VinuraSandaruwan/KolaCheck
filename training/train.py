"""Train MobileNetV2 and export KolaCheck's TFLite model.

Usage from the training directory:
    python train.py ../data

The supplied base-image split from ../data-source is required. Its base IDs
keep each original grouped with any offline variants; this script trains from
the standardized originals and applies online augmentation. Validation metrics
select model settings; the separate TFLite evaluator measures the test split.
"""
import csv
import hashlib
import json
import pathlib
import sys

import numpy as np
import tensorflow as tf
from tensorflow import keras


PROJECT = pathlib.Path(__file__).resolve().parents[1]
DATA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data").resolve()
OUT = PROJECT / "app" / "assets"
METRICS = pathlib.Path(__file__).resolve().parent / "metrics.json"
IMG, BATCH, SEED = 224, 32, 42
EXPECTED_CLASSES = [
    "algal_leaf_spot", "black_blight", "blister_blight",
    "gray_blight", "healthy", "spider_mite",
]
keras.utils.set_random_seed(SEED)
try:
    tf.config.experimental.enable_op_determinism()
except (AttributeError, RuntimeError):
    pass

classes = sorted(p.name for p in DATA.iterdir() if p.is_dir())
if classes != EXPECTED_CLASSES:
    raise ValueError(f"Expected class folders {EXPECTED_CLASSES}; found {classes}")
class_to_index = {name: index for index, name in enumerate(classes)}
files = {}
for class_dir in sorted(DATA.iterdir()):
    if not class_dir.is_dir():
        continue
    for path in sorted(class_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"}:
            if path.stem in files:
                raise ValueError(f"Duplicate image ID across folders: {path.stem}")
            files[path.stem] = (path, class_to_index[class_dir.name])

metadata = PROJECT / "data-source" / "Sri Lankan Tea Leaf Dataset" / "metadata files"
split_files = {
    "train": metadata / "train_original_plus_augmented_baseid_split.csv",
    "validation": metadata / "validation_original_only_baseid_split.csv",
    "test": metadata / "test_original_only_baseid_split.csv",
}
if all(path.is_file() for path in split_files.values()):
    partitions = {}
    manifest_classes = {}
    folder_aliases = {
        "algal_leaf_spot": "algal_leaf_spot",
        "black_blight": "black_blight",
        "blister_blight": "blister_blight",
        "gray_blight": "gray_blight",
        "healthy": "healthy",
        "spider_mites": "spider_mite",
        "spider_mite": "spider_mite",
    }
    for name, path in split_files.items():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        ids = set()
        for row in rows:
            image_id = row["base_id"].strip()
            manifest_label = row["class_label"].strip().lower().replace(" ", "_")
            canonical_label = folder_aliases.get(manifest_label)
            if not image_id or canonical_label is None:
                raise ValueError(f"Invalid image ID or class label in {path.name}: {row}")
            previous = manifest_classes.setdefault(image_id, canonical_label)
            if previous != canonical_label:
                raise ValueError(f"Base image {image_id} appears under multiple class labels")
            ids.add(image_id)
        partitions[name] = ids
    if (partitions["train"] & partitions["validation"] or
            partitions["train"] & partitions["test"] or
            partitions["validation"] & partitions["test"]):
        raise ValueError("Dataset split manifests contain overlapping base IDs")
    if set(files) != set.union(*partitions.values()):
        raise ValueError("Split manifests do not cover the image files under DATA")
    for image_id, (_, class_index) in files.items():
        manifest_label = manifest_classes.get(image_id)
        if manifest_label != classes[class_index]:
            raise ValueError(
                f"Label mismatch for {image_id}: folder={classes[class_index]}, manifest={manifest_label}"
            )
    print("Using supplied base-image train/validation/test split.")
else:
    raise FileNotFoundError(
        f"Leakage-safe split metadata not found under {metadata}. "
        "Place the dataset metadata files there before training."
    )

print("Classes:", classes)
print("Images per split:", {
    name: {
        "total": sum(image_id in files for image_id in ids),
        "by_class": {
            class_name: sum(
                image_id in files and files[image_id][1] == class_to_index[class_name]
                for image_id in ids
            )
            for class_name in classes
        },
    }
    for name, ids in partitions.items()
})

AUTOTUNE = tf.data.AUTOTUNE

def make_dataset(image_ids, shuffle=False):
    present_ids = sorted(image_id for image_id in image_ids if image_id in files)
    paths = [str(files[image_id][0]) for image_id in present_ids]
    labels = [files[image_id][1] for image_id in present_ids]
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))
    if shuffle:
        dataset = dataset.shuffle(len(paths), seed=SEED, reshuffle_each_iteration=True)

    def load_image(path, label):
        image = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        image = tf.image.resize(image, (IMG, IMG))
        return image, label

    return dataset.map(load_image, num_parallel_calls=AUTOTUNE).batch(BATCH).prefetch(AUTOTUNE)

train = make_dataset(partitions["train"], shuffle=True)
val = make_dataset(partitions["validation"])

augment = keras.Sequential([
    keras.layers.RandomFlip("horizontal_and_vertical"),
    keras.layers.RandomRotation(0.15),
    keras.layers.RandomZoom(0.15),
    keras.layers.RandomContrast(0.25),
    keras.layers.RandomBrightness(0.25),
])
base = keras.applications.MobileNetV2(
    input_shape=(IMG, IMG, 3), include_top=False, weights="imagenet")
base.trainable = False

inp = keras.Input((IMG, IMG, 3))
x = augment(inp)
x = keras.layers.Rescaling(1 / 127.5, offset=-1)(x)
x = base(x, training=False)
x = keras.layers.GlobalAveragePooling2D()(x)
x = keras.layers.Dropout(0.25)(x)
out = keras.layers.Dense(len(classes), activation="softmax")(x)
model = keras.Model(inp, out)

callbacks = [keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)]
model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
model.fit(train, validation_data=val, epochs=10, callbacks=callbacks, shuffle=False)

base.trainable = True
for layer in base.layers[:-30]:
    layer.trainable = False
model.compile(optimizer=keras.optimizers.Adam(1e-5), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
model.fit(train, validation_data=val, epochs=10, callbacks=callbacks, shuffle=False)

# Use validation metrics for model development. Keep the test partition out of
# training and selection; run evaluate_tflite.py only for a final benchmark.
y_true = np.concatenate([labels.numpy() for _, labels in val])
y_pred = np.argmax(model.predict(val), axis=1)
cm_array = np.zeros((len(classes), len(classes)), dtype=np.int64)
for truth, prediction in zip(y_true, y_pred):
    cm_array[int(truth), int(prediction)] += 1
cm = cm_array.tolist()
total = int(cm_array.sum())
correct = int(np.trace(cm_array))
report = {}
for index, class_name in enumerate(classes):
    true_positive = int(cm_array[index, index])
    support = int(cm_array[index, :].sum())
    predicted = int(cm_array[:, index].sum())
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / support if support else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    report[class_name] = {
        "precision": precision, "recall": recall, "f1-score": f1, "support": support,
    }
report["accuracy"] = correct / total if total else 0.0
for average_name in ("macro avg", "weighted avg"):
    weights = [1.0] * len(classes) if average_name == "macro avg" else [
        report[name]["support"] for name in classes
    ]
    weight_total = sum(weights)
    report[average_name] = {
        key: (sum(report[name][key] * weight for name, weight in zip(classes, weights)) / weight_total
              if weight_total else 0.0)
        for key in ("precision", "recall", "f1-score")
    }
    report[average_name]["support"] = total
metrics = {
    "dataset": "SLTeaLeaf standardized originals",
    "evaluation_split": "validation_original_only_baseid_split",
    "split_method": "provided base_image_id grouped split",
    "model_architecture": "MobileNetV2 ImageNet weights, 224x224, fine-tuned final 30 layers",
    "training_seed": SEED,
    "tensorflow_version": tf.__version__,
    "training_config": {
        "input_size": IMG,
        "batch_size": BATCH,
        "head_epochs_max": 10,
        "fine_tune_epochs_max": 10,
        "fine_tune_unfrozen_layers": 30,
        "head_learning_rate": 1e-3,
        "fine_tune_learning_rate": 1e-5,
        "early_stopping": {"monitor": "val_loss", "patience": 3, "restore_best_weights": True},
        "online_augmentation": ["horizontal_flip", "vertical_flip", "rotation", "zoom", "contrast", "brightness"],
    },
    "dataset_image_counts": {
        class_name: sum(class_index == class_to_index[class_name] for _, class_index in files.values())
        for class_name in classes
    },
    "sample_counts": {name: sum(image_id in files for image_id in ids)
                      for name, ids in partitions.items()},
    "validation_report": report,
    "validation_confusion_matrix": cm,
    "classes": classes,
}
METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
print("Test confusion matrix:\\n", cm_array)
OUT.mkdir(parents=True, exist_ok=True)
tflite = tf.lite.TFLiteConverter.from_keras_model(model)
# Keep float weights: the prior dynamic-range-quantized export lost 3.2 points
# versus Keras on the same held-out split. Model size grows, but inference
# quality matters more for this small pilot and the artifact remains mobile-sized.
model_bytes = tflite.convert()
(OUT / "model.tflite").write_bytes(model_bytes)
(OUT / "labels.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
metrics["model_artifact"] = {
    "file": "app/assets/model.tflite",
    "sha256": hashlib.sha256(model_bytes).hexdigest(),
    "size_bytes": len(model_bytes),
    "export": "float weights; no post-training weight quantization",
}
METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
print("Saved model.tflite and labels.txt to", OUT.resolve())


