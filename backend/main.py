"""KolaCheck local API: image inference plus scan-event storage."""
from __future__ import annotations

from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
import logging
import os
import random
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from starlette.concurrency import run_in_threadpool

from model import InvalidImageError, ModelRuntimeError, TeaLeafPredictor

logger = logging.getLogger("kolacheck.api")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PAGE_SIZE = 1000
ENVIRONMENT = os.getenv("APP_ENV", "development").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if bool(SUPABASE_URL) != bool(SUPABASE_KEY):
    raise RuntimeError("Set both SUPABASE_URL and SUPABASE_KEY, or neither for local in-memory mode")
if ENVIRONMENT == "production":
    raise RuntimeError("Production mode is disabled until authenticated society access is implemented")

sb = None
if SUPABASE_URL and SUPABASE_KEY:
    from supabase import create_client

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)


class DiseaseLabel(str, Enum):
    algal_leaf_spot = "algal_leaf_spot"
    black_blight = "black_blight"
    blister_blight = "blister_blight"
    gray_blight = "gray_blight"
    healthy = "healthy"
    spider_mite = "spider_mite"


ShortId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ScanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: DiseaseLabel
    confidence: Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
    society_id: ShortId = "demo"
    device_id: ShortId = "anon"
    model_version: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] = None
    lat: Annotated[float | None, Field(ge=-90, le=90, allow_inf_nan=False)] = None
    lon: Annotated[float | None, Field(ge=-180, le=180, allow_inf_nan=False)] = None

    @model_validator(mode="after")
    def coordinates_must_be_paired(self) -> "ScanCreate":
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be provided together")
        return self


class ScanCreated(BaseModel):
    ok: bool = True
    scan_id: str
    created_at: datetime


class PredictionItem(BaseModel):
    label: DiseaseLabel
    confidence: float


class PredictionResponse(BaseModel):
    label: DiseaseLabel
    confidence: float
    needs_review: bool
    top_predictions: list[PredictionItem]
    model_version: str


class ScanSummary(BaseModel):
    total: int
    counts: dict[str, int]
    demo_rows: int
    diseased_share: float


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.predictor = TeaLeafPredictor()
    if sb is None:
        logger.warning("No Supabase credentials configured; scans are stored in memory and reset on restart")
    yield
    application.state.predictor = None


app = FastAPI(
    title="KolaCheck API",
    description="Tea-leaf image prediction and scan-event API. Local/demo mode only; public production access is not enabled.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if getattr(app.state, "predictor", None) is None:
        raise HTTPException(status_code=503, detail="Model is not ready")
    return {"status": "ready", "model_version": app.state.predictor.model_version}


def _insert_scan(scan: ScanCreate, *, is_demo: bool = False) -> ScanCreated:
    created_at = datetime.now(timezone.utc)
    row = {
        **scan.model_dump(mode="json"),
        "label": scan.label.value,
        "created_at": created_at.isoformat(),
        "is_demo": is_demo,
    }
    if sb is None:
        scan_id = str(uuid4())
        _MEMORY_SCANS.append({"id": scan_id, **row})
        return ScanCreated(scan_id=scan_id, created_at=created_at)

    try:
        response = sb.table("scans").insert(row).execute()
        saved = response.data[0]
        return ScanCreated(scan_id=str(saved["id"]), created_at=saved["created_at"])
    except Exception as exc:
        logger.exception("Could not persist scan")
        raise HTTPException(status_code=503, detail="Scan storage is temporarily unavailable") from exc


_MEMORY_SCANS: list[dict[str, Any]] = []


@app.post("/api/v1/scans", response_model=ScanCreated, status_code=201, tags=["scans"])
def create_scan(scan: ScanCreate) -> ScanCreated:
    return _insert_scan(scan)


@app.post("/api/scans", response_model=ScanCreated, include_in_schema=False)
def create_scan_legacy(scan: ScanCreate) -> ScanCreated:
    """Compatibility route used by the existing mobile client."""
    return _insert_scan(scan)


@app.post(
    "/api/v1/predictions",
    response_model=PredictionResponse,
    tags=["predictions"],
    description=(
        "Run the packaged TFLite model on a close-up leaf image. Confidence is the model's "
        "softmax score, not a calibrated probability; needs_review is a 0.60 score heuristic."
    ),
)
async def create_prediction(
    file: Annotated[UploadFile, File(description="JPEG, PNG, or WebP tea-leaf image; maximum 10 MiB")],
) -> PredictionResponse:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MiB upload limit")
    try:
        result = await run_in_threadpool(app.state.predictor.predict, content)
    except InvalidImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelRuntimeError as exc:
        logger.exception("TFLite inference failed")
        raise HTTPException(status_code=500, detail="Model inference failed") from exc
    return PredictionResponse(**result)


def _read_society_scans(society_id: str) -> list[dict[str, Any]]:
    if sb is None:
        return [row for row in _MEMORY_SCANS if row["society_id"] == society_id]

    rows: list[dict[str, Any]] = []
    offset = 0
    try:
        while True:
            response = (
                sb.table("scans")
                .select("id,label,created_at,is_demo")
                .eq("society_id", society_id)
                .order("id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            )
            page = response.data or []
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                return rows
            offset += len(page)
    except Exception as exc:
        logger.exception("Could not read scan summary")
        raise HTTPException(status_code=503, detail="Scan summary is temporarily unavailable") from exc


def _make_summary(society_id: str) -> ScanSummary:
    rows = _read_society_scans(society_id)
    counts = Counter(row["label"] for row in rows)
    diseased_count = sum(count for label, count in counts.items() if label != DiseaseLabel.healthy.value)
    return ScanSummary(
        total=len(rows),
        counts=dict(counts),
        demo_rows=sum(1 for row in rows if row.get("is_demo", False)),
        diseased_share=round(diseased_count / len(rows), 3) if rows else 0.0,
    )


@app.get(
    "/api/v1/societies/{society_id}/scan-summary",
    response_model=ScanSummary,
    tags=["summaries"],
)
def get_scan_summary(society_id: ShortId) -> ScanSummary:
    return _make_summary(society_id)


@app.get("/api/summary", response_model=ScanSummary, include_in_schema=False)
def get_scan_summary_legacy(society_id: ShortId = "demo") -> ScanSummary:
    """Compatibility route used by the existing dashboard."""
    return _make_summary(society_id)


@app.post("/api/v1/demo/seed", tags=["development"])
def seed_demo_scans(count: Annotated[int, Query(ge=1, le=500)] = 40) -> dict[str, int]:
    if sb is not None:
        raise HTTPException(status_code=404, detail="Demo seeding is available only in local in-memory mode")
    labels = list(DiseaseLabel)
    now = datetime.now(timezone.utc)
    for _ in range(count):
        scan = ScanCreate(
            label=random.choice(labels),
            confidence=round(random.uniform(0.6, 0.99), 2),
            society_id="demo",
            device_id="seed",
        )
        _insert_scan(scan, is_demo=True)
        _MEMORY_SCANS[-1]["created_at"] = (now - timedelta(days=random.randint(0, 20))).isoformat()
    return {"seeded": count}


@app.post("/api/demo-seed", include_in_schema=False)
def seed_demo_scans_legacy(n: Annotated[int, Query(ge=1, le=500)] = 40) -> dict[str, int]:
    return seed_demo_scans(n)


PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>KolaCheck Society Dashboard</title>
<style>body{font-family:system-ui;max-width:640px;margin:24px auto;padding:0 16px}
.r{display:flex;align-items:center;gap:8px;margin:6px 0}.b{background:#2e7d32;height:18px;border-radius:4px}
.w{background:#fff3cd;padding:8px;border-radius:6px;display:none}</style>
<h2>KolaCheck: disease trends for your society</h2><div id=w class=w></div><p id=t></p><div id=c></div>
<script>fetch('/api/v1/societies/demo/scan-summary').then(r=>{if(!r.ok)throw new Error('summary unavailable');return r.json()}).then(d=>{
t.textContent=d.total+' scans, '+Math.round(d.diseased_share*100)+'% showing a disease';
if(d.demo_rows){w.style.display='block';w.textContent='Includes '+d.demo_rows+' DEMO rows (not real grower data)'}
const m=Math.max(1,...Object.values(d.counts));
c.innerHTML=Object.entries(d.counts).sort((a,b)=>b[1]-a[1]).map(([k,v])=>
`<div class=r><span style="width:140px">${k.replaceAll('_',' ')}</span><div class=b style="width:${v/m*300}px"></div>${v}</div>`).join('')
}).catch(()=>{t.textContent='Could not load scan summary.'})</script>"""


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return PAGE
