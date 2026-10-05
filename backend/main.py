"""KolaCheck API. Run: uvicorn main:app --host 0.0.0.0 --port 8000
Env (optional): SUPABASE_URL, SUPABASE_KEY. Without them, data is kept in memory (demo)."""
import os, random
from collections import Counter
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

LABELS = {"algal_leaf_spot", "black_blight", "blister_blight",
          "gray_blight", "healthy", "spider_mite"}
app = FastAPI(title="KolaCheck API")
sb, MEM = None, []
if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

class Scan(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    society_id: str = "demo"
    device_id: str = "anon"
    lat: float | None = None
    lon: float | None = None

def _save(row):
    if sb: sb.table("scans").insert(row).execute()
    else: MEM.append(row)

@app.post("/api/scans")
def add_scan(s: Scan):
    if s.label not in LABELS: raise HTTPException(422, "unknown label")
    _save({**s.model_dump(), "created_at": datetime.now(timezone.utc).isoformat(), "is_demo": False})
    return {"ok": True}

@app.get("/api/summary")
def summary(society_id: str = "demo"):
    if sb:
        rows = sb.table("scans").select("label,created_at,is_demo").eq("society_id", society_id).execute().data
    else:
        rows = [r for r in MEM if r["society_id"] == society_id]
    diseased = [r for r in rows if r["label"] != "healthy"]
    return {"total": len(rows), "counts": Counter(r["label"] for r in rows),
            "demo_rows": sum(1 for r in rows if r.get("is_demo")),
            "diseased_share": round(len(diseased) / len(rows), 3) if rows else 0}

@app.post("/api/demo-seed")
def seed(n: int = 40):
    """FAKE data for the demo video only. Dashboard flags it. Say so in your pitch."""
    now = datetime.now(timezone.utc)
    for _ in range(n):
        _save({"label": random.choice(sorted(LABELS)), "confidence": round(random.uniform(.6, .99), 2),
               "society_id": "demo", "device_id": "seed", "lat": None, "lon": None,
               "created_at": (now - timedelta(days=random.randint(0, 20))).isoformat(), "is_demo": True})
    return {"seeded": n}

PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>KolaCheck Society Dashboard</title>
<style>body{font-family:system-ui;max-width:640px;margin:24px auto;padding:0 16px}
.r{display:flex;align-items:center;gap:8px;margin:6px 0}.b{background:#2e7d32;height:18px;border-radius:4px}
.w{background:#fff3cd;padding:8px;border-radius:6px;display:none}</style>
<h2>KolaCheck: disease trends for your society</h2><div id=w class=w></div><p id=t></p><div id=c></div>
<script>fetch('/api/summary').then(r=>r.json()).then(d=>{
t.textContent=d.total+' scans, '+Math.round(d.diseased_share*100)+'% showing a disease';
if(d.demo_rows){w.style.display='block';w.textContent='Includes '+d.demo_rows+' DEMO rows (not real grower data)'}
const m=Math.max(1,...Object.values(d.counts));
c.innerHTML=Object.entries(d.counts).sort((a,b)=>b[1]-a[1]).map(([k,v])=>
`<div class=r><span style="width:140px">${k.replaceAll('_',' ')}</span><div class=b style="width:${v/m*300}px"></div>${v}</div>`).join('')})</script>"""

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(): return PAGE
