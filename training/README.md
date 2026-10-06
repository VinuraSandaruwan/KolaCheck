# Train and evaluate the tea-leaf model

Use Python 3.12 and the six standardized class folders under `../data`. Training fails early when the folder names, image IDs, split membership, or labels disagree with the supplied metadata.

## Train and export

From Command Prompt:

```cmd
cd /d "D:\Projects\Competitions\IntelliCon'26\Solution\kolacheck\training"
.venv\Scripts\activate.bat
python train.py ..\data
```

The script uses the supplied base-image-grouped split: 1,065 train, 188 validation, 538 test originals. It uses the validation partition for model-development metrics and does not use the test partition to select weights. Training uses random on-the-fly image augmentation; it does not load the metadata package's 4,177 offline variants. It writes the validation report and the TFLite artifact to `app/assets`.

The export now keeps float weights because the prior compressed export scored lower than its Keras model on the same holdout. Expect a larger `.tflite` file. Compare measured quality and size before changing back to quantization.

The previous compressed artifact and its report are retained here for local comparison: `baseline_dynamic_quantized.tflite` and `metrics_baseline_dynamic_quantized.json`. The app and API load only `app/assets/model.tflite`.

## Evaluate the actual API model

```cmd
python evaluate_tflite.py ..\data
```

This evaluates the packaged `.tflite` artifact through the same predictor and resize logic used by the backend API. `metrics.json` records overall and per-class precision/recall/F1, a confusion matrix, image acquisition-condition results, the model hash, and the held-out sample count. The supplied test split has already been used to compare artifacts; do not use it to tune future versions. Collect a new independent field-photo set for final claims.

## Practical improvement loop

1. Review the confusion matrix and have a tea-disease specialist check the confusing labels, especially gray blight versus healthy/other blights.
2. Collect more correctly labeled images for the weak classes and difficult conditions. The current set has 126 blister-blight and 138 spider-mite images, and only 1,791 originals overall.
3. Keep every photo of the same leaf, plant, plot, or capture session in one split. The supplied split groups by base image ID; a later field dataset should also group by plant/site/session to measure generalization.
4. Add new images to training/validation partitions only. Keep a new, untouched field-photo set for final evaluation; do not tune thresholds or training settings against it.
5. Compare candidates on validation data during development. Use the final field-photo set once for the deployment check. Record model hash, size, per-class recall, and acquisition-condition results. Do not report only overall accuracy.

The supplied images are already visually screened, cropped around leaves/symptoms where required, standardized to RGB 1024x1024, and padded to square. Real uncropped phone photos have not been validated; treat the current scores as dataset performance only.
