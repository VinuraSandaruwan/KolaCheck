"""KolaCheck training: MobileNetV2 transfer learning -> TFLite.
Usage: python train.py /path/to/data   (data/<class_name>/*.jpg)
Folder names must be: algal_leaf_spot black_blight blister_blight gray_blight healthy spider_mite
"""
import json, pathlib, sys
import numpy as np
import tensorflow as tf
from tensorflow import keras
from sklearn.metrics import classification_report, confusion_matrix

DATA = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
OUT = pathlib.Path("../app/assets"); OUT.mkdir(parents=True, exist_ok=True)
IMG, BATCH, SEED = 224, 32, 42

train = keras.utils.image_dataset_from_directory(
    DATA, validation_split=0.2, subset="training", seed=SEED,
    image_size=(IMG, IMG), batch_size=BATCH)
val = keras.utils.image_dataset_from_directory(
    DATA, validation_split=0.2, subset="validation", seed=SEED,
    image_size=(IMG, IMG), batch_size=BATCH, shuffle=False)
classes = train.class_names
print("Classes:", classes)
AUTOTUNE = tf.data.AUTOTUNE
train, val = train.prefetch(AUTOTUNE), val.prefetch(AUTOTUNE)

augment = keras.Sequential([
    keras.layers.RandomFlip("horizontal_and_vertical"),
    keras.layers.RandomRotation(0.15),
    keras.layers.RandomZoom(0.15),
    keras.layers.RandomContrast(0.25),   # real phone photos: uneven light
    keras.layers.RandomBrightness(0.25),
])
base = keras.applications.MobileNetV2(
    input_shape=(IMG, IMG, 3), include_top=False, weights="imagenet")
base.trainable = False

inp = keras.Input((IMG, IMG, 3))              # raw 0-255 pixels (app sends the same)
x = augment(inp)
x = keras.layers.Rescaling(1 / 127.5, offset=-1)(x)
x = base(x, training=False)
x = keras.layers.GlobalAveragePooling2D()(x)
x = keras.layers.Dropout(0.25)(x)
out = keras.layers.Dense(len(classes), activation="softmax")(x)
model = keras.Model(inp, out)

cb = [keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)]
model.compile(keras.optimizers.Adam(1e-3), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(train, validation_data=val, epochs=10, callbacks=cb)

base.trainable = True                          # fine-tune top layers
for layer in base.layers[:-30]:
    layer.trainable = False
model.compile(keras.optimizers.Adam(1e-5), "sparse_categorical_crossentropy", ["accuracy"])
model.fit(train, validation_data=val, epochs=10, callbacks=cb)

y_true = np.concatenate([y.numpy() for _, y in val])
y_pred = np.argmax(model.predict(val), axis=1)
report = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
cm = confusion_matrix(y_true, y_pred).tolist()
json.dump({"report": report, "confusion_matrix": cm, "classes": classes},
          open("metrics.json", "w"), indent=2)
print(classification_report(y_true, y_pred, target_names=classes))
print("Confusion matrix:\n", np.array(cm))

tflite = tf.lite.TFLiteConverter.from_keras_model(model)
tflite.optimizations = [tf.lite.Optimize.DEFAULT]
(OUT / "model.tflite").write_bytes(tflite.convert())
(OUT / "labels.txt").write_text("\n".join(classes) + "\n")
print("Saved model.tflite and labels.txt to", OUT.resolve())
