from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.orchestrator.context import AnalyzeRequest, RunContext
from app.orchestrator import jobs as analyze_jobs
from app.orchestrator.response import analyze_result_dict
from app.orchestrator.runner import run_pipeline
from app.rag.ingest import ensure_sop_ingested


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_sop_ingested()
    yield


app = FastAPI(title="SEO Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(body: AnalyzeRequest) -> JSONResponse:
    ctx = RunContext(request=body)
    run_pipeline(ctx)
    code, payload = analyze_result_dict(ctx)
    return JSONResponse(status_code=code, content=payload)


@app.post("/analyze/async")
def analyze_async(body: AnalyzeRequest) -> JSONResponse:
    job_id = analyze_jobs.start_job(body)
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "poll_path": f"/analyze/jobs/{job_id}",
        },
    )


@app.get("/analyze/jobs/{job_id}")
def analyze_job_status(job_id: str, since: int = 0) -> dict:
    snap = analyze_jobs.get_snapshot(job_id, since=since)
    if snap is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return snap


_frontend = Path(__file__).resolve().parent / "frontend"
if _frontend.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_frontend), html=True), name="ui")
