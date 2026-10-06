# KolaCheck backend and model API

This API loads `../app/assets/model.tflite` at startup. It can run image inference without Flutter, accept scan records, and return society summaries. It is for local/demo use only: society access is not authenticated, so do not expose it publicly.

## Run on Windows

From Command Prompt:

```cmd
cd /d "D:\Projects\Competitions\IntelliCon'26\Solution\kolacheck\backend"
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Use port `8001` if another app already occupies `8000`. Keep the window open. Open `http://127.0.0.1:8001/docs` to exercise the API.

## API routes

- `GET /health/live` — confirms the process responds.
- `GET /health/ready` — confirms the model loaded; includes its model version hash.
- `POST /api/v1/predictions` — upload a JPEG, PNG, or WebP image as multipart form field `file` (maximum 10 MiB). Runs the packaged TFLite model and returns the top label, score, review flag, top three results, and model version. It does not store a scan.
- `POST /api/v1/scans` — store a prediction result as a scan event. Returns `201 Created`.
- `GET /api/v1/societies/{society_id}/scan-summary` — aggregate stored scans for a society.
- `POST /api/v1/demo/seed?count=40` — generate fake in-memory demo rows. Local only; unavailable when Supabase is configured.

Example image prediction from Command Prompt:

```cmd
curl.exe -X POST "http://127.0.0.1:8001/api/v1/predictions" -F "file=@D:\path\to\leaf.jpg"
```

Then, if you want that result in the scan summary, copy the returned `label`, `confidence`, and `model_version` into a `POST /api/v1/scans` JSON request in `/docs`.

## Storage and model notes

Without Supabase credentials, scan records are kept in memory and reset when the server stops. With Supabase, set both `SUPABASE_URL` and `SUPABASE_KEY` before starting the server; keep the service key server-side. The service currently has no sign-in or society authorization, so production mode intentionally refuses to start.

The API and evaluation script use one TFLite predictor and one image-resize implementation. Input images should be close-up, single-leaf images similar to the supplied cropped/standardized dataset. Results on uncropped phone photos are not yet validated.

Run the held-out evaluation from `training`:

```cmd
cd /d "D:\Projects\Competitions\IntelliCon'26\Solution\kolacheck\training"
.venv\Scripts\activate.bat
python evaluate_tflite.py ..\data
```
