# KolaCheck: Gate 2 Step-by-Step Guide (team of two)

Roles: **Person A** = model + backend. **Person B** = app + grower outreach. Interviews together where possible.

## The truth about where you stand
You have Route B (desk research only). Judges can see that. The cheapest way to move your score is **5+ real grower conversations** with real quotes in your pitch. A working app with no validation loses to a simpler app with validation. Do Step 7 in parallel with everything else, starting tomorrow.

---
## Step 1. Set up tools (Both, 1-2 hours)
- Install Flutter (flutter.dev/install), Android Studio (for SDK), run `flutter doctor` until Android toolchain is green.
- Python 3.10-3.12 + `python -m venv venv`.
- Phone: enable Developer Options + USB debugging.

Git hosting is not required for local model/backend testing.

## Step 2. Get the dataset (Person A, 1 hour)
1. Open data.mendeley.com/datasets/sjmy6k24d6/3, download, unzip.
2. Arrange as `data/<class>/*.jpg` using EXACTLY these folder names: `algal_leaf_spot, black_blight, blister_blight, gray_blight, healthy, spider_mite`. Rename folders if the dataset names differ.
3. Count images per class (`ls data/x | wc -l`). Write the counts down for your AI usage report.
4. Look at 20 images per class yourself. Note: lighting, background, duplicates of the same leaf. Near-duplicate photos split across train and validation inflate accuracy. If images are numbered in series from one leaf, move whole series into one split manually, or tell judges the risk.
5. Read the dataset licence (usually CC BY 4.0) and keep the citation already in your proposal.

## Step 3. Train the model (Person A, 2-4 hours)
```
cd training
pip install -r requirements.txt
python train.py ../data
```
(Free GPU: upload `train.py` and data to Google Colab, then download `model.tflite`, `labels.txt`, `metrics.json`.)
- Output: `app/assets/model.tflite`, `labels.txt`, `metrics.json`.
- Read the per-class precision/recall and confusion matrix. Write down which classes get confused (likely blister vs black vs gray blight).
- Run `python evaluate_tflite.py ../data` to evaluate the exported model that the backend actually serves; review the field/controlled condition breakdown in `metrics.json`.
- If accuracy is below ~80%: more epochs, check for mislabelled images, merge impossible-to-separate classes. **Report the real number even if modest.** Never quote a number you did not measure.
- Check `labels.txt` order matches what the app shows (it is loaded from the file, so it always does).

## Step 4. Real-world test (Both, 1 hour. This is your biggest differentiator)
Dataset photos are cleaner than phone photos. Take 30+ photos of real tea leaves (or find a tea plot / ask a grower/estate), under shade, sun, and wet leaves. Run them through the app, record correct/incorrect in a table. Report "dataset accuracy X%, real phone photo accuracy Y% on N photos". Judges reward this honesty.
If you cannot reach tea plants, test with printed or on-screen leaf images from the dataset photographed with your phone, and say exactly that.

## Step 5. Run the backend (Person A, 1 hour)
1. Supabase: create a free project, SQL Editor, paste `backend/schema.sql`, run.
2. Settings > API: copy project URL and the **service_role key** (secret, never commit it).
3. ```
   cd backend && pip install -r requirements.txt
   export SUPABASE_URL=... SUPABASE_KEY=...
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Skip the env vars to run in-memory for a quick local test. Run `uvicorn main:app --host 127.0.0.1 --port 8000` from `backend`.
4. Open `http://localhost:8000/docs`. Use `POST /api/v1/predictions` to upload an image and test inference. Use `POST /api/v1/scans` to save a result and `GET /api/v1/societies/demo/scan-summary` to inspect the summary. `/api/v1/demo/seed` creates fake in-memory rows for a demo only.
5. The backend has no sign-in or society authorization yet; keep it on localhost and do not expose it publicly.

## Step 6. Build the app (Person B, 2-3 hours)
```
cd app
flutter create .          # generates android/ ios/ folders; keep our lib/ and pubspec.yaml
flutter pub get
```
(If `flutter create` overwrote pubspec.yaml, restore ours: it has the assets and packages.)
1. Edit `android/app/build.gradle(.kts)`: set `minSdk = 26`.
2. In `android/app/src/main/AndroidManifest.xml` add inside `<manifest>`: `<uses-permission android:name="android.permission.INTERNET"/>` and `<uses-permission android:name="android.permission.CAMERA"/>`; add `android:usesCleartextTraffic="true"` to `<application>` (needed for http to your laptop).
3. Make sure `assets/model.tflite` exists (from Step 3).
4. In `lib/main.dart` set `backendUrl` to your laptop IP (`ipconfig`/`ifconfig`).
5. `flutter run` with the phone on USB. Test: camera, gallery, language switch, airplane mode (should show "waiting to sync", then sync when back online).
6. Build APK for the demo: `flutter build apk --release`.
If the on-device model fails to load, read the error shown in-app; most common causes are a missing asset or `minSdk`. Fallback plan: serve prediction from FastAPI (tell judges honestly).

## Step 7. Grower validation (Person B leads, start now, 5+ conversations)
Where: the TSHDA / Tea Smallholding Development Society office in Galle or Matara, tea collection centres, tea shops near smallholdings, relatives of friends in Southern Province. Also post a short survey (Google Form) in Sri Lankan farmer/tea Facebook and WhatsApp groups. Ask in Sinhala.
Ask (do not pitch):
1. How do you know when a leaf is sick? Who do you ask?
2. Last time you saw disease, what was it, how long before you acted, what did it cost you?
3. When did an extension officer last visit?
4. Do you have a smartphone? Do you use WhatsApp/camera? Signal on your plot?
5. What would make you trust an app? What would make you ignore it?
6. Would your society use a dashboard of disease reports?
Record: date, district, role, 2-3 direct quotes (get permission, anonymise names). Show them the app on your phone and watch them use it; note where they hesitate. Update the three assumptions in your proposal as confirmed / wrong / unclear. If something contradicts you, **change the product** and say so.

## Step 8. Gate 2 deliverables (Both)
- **Architecture diagram**: the mermaid chart in `README.md` renders on GitHub; also screenshot it (or draw in draw.io).
- **Public repo**: README, setup steps, `metrics.json`, no secrets (add `.gitignore` for `data/`, `*.env`, `build/`).
- **Screen recording** (60-90 s, screen-record the phone): open app, switch language, scan a leaf, show result and "ask officer" line, show low-confidence message, show dashboard.
- Record early, record twice, keep the better take.

## Step 9. Week 3 (4-11 Oct)
- Polish text from grower feedback (probably explanation wording and language).
- Business case: free for growers, annual fee for societies, supplier placements (leave society/supplier revenue unsized unless a society gives you a number).
- Pitch deck, 8-10 slides: problem (with grower quotes), solution demo, validation results, real accuracy, market, model, risks, next steps.
- AI usage report: what you used AI for (code scaffolding, translations), what you verified yourselves, where the model fails.
- Get a native Sinhala and Tamil speaker (ideally a grower) to review `advice.dart`.

## Risk control
| Risk | Plan |
|---|---|
| Low field accuracy | Report it, raise `unsureBelow`, reduce to fewer classes |
| Can't reach growers | Society office first, then survey; report counts honestly |
| On-device model fails | Server-side inference fallback, say so |
| Demo day crash | Pre-recorded video + APK installed + backend running in-memory |
