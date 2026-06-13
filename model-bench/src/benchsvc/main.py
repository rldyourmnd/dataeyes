from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from benchsvc import __version__
from benchsvc.benchmarks import BenchmarkRunner
from benchsvc.db import SessionLocal, get_db
from benchsvc.llm_client import DataEyesClient
from benchsvc.models import BenchmarkRun, ModelResult
from benchsvc.schemas import BenchmarkRunRequest, BenchmarkRunResponse, DiscoverModelsResponse
from benchsvc.settings import get_settings
from benchsvc.storage import ArtifactStore

app = FastAPI(title="DataEyes Model Benchmark", version=__version__)


@app.get("/health")
def health() -> dict:
    settings = get_settings()

    # Database check
    db_status = "unknown"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    # LiteLLM proxy check — use /v1/models since /health returns empty on some versions
    litellm_status = "unknown"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{settings.litellm_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
        litellm_status = "ok" if resp.status_code < 500 else f"error: {resp.status_code}"
    except Exception as exc:
        litellm_status = f"error: {type(exc).__name__}"

    # Artifact storage check (ping S3 endpoint or verify local dir)
    artifact_status = "unknown"
    try:
        if settings.artifact_storage_mode.lower() == "s3":
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(settings.rustfs_endpoint_url)
            artifact_status = "ok" if resp.status_code < 500 else f"error: {resp.status_code}"
        else:
            import os

            os.makedirs(settings.local_artifact_dir, exist_ok=True)
            artifact_status = "ok"
    except Exception as exc:
        artifact_status = f"error: {type(exc).__name__}"

    all_ok = db_status == "ok" and litellm_status == "ok" and artifact_status == "ok"
    return {
        "status": "ok" if all_ok else "degraded",
        "version": __version__,
        "database": db_status,
        "artifact_storage": artifact_status,
        "litellm_proxy": litellm_status,
    }


@app.get("/models/discover", response_model=DiscoverModelsResponse)
def discover_models(include_raw: bool = False) -> DiscoverModelsResponse:
    settings = get_settings()
    try:
        models = DataEyesClient(settings).list_models(include_raw=include_raw)
        return DiscoverModelsResponse(
            base_url=settings.dataeyes_llm_base_url, count=len(models), models=models
        )
    except Exception as exc:
        return DiscoverModelsResponse(
            base_url=settings.dataeyes_llm_base_url,
            count=0,
            models=[],
            error={"type": type(exc).__name__, "message": str(exc)},
        )


@app.get("/benchmarks/cases")
def benchmark_cases() -> dict:
    return {
        "suites": [
            "smoke",
            "json_schema",
            "tool_call",
            "agent_mini",
            "latency_repeated",
            "standard",
        ],
        "cases": [
            {
                "case_id": "smoke_json_exact",
                "suite": "smoke",
                "description": "Exact JSON and latency smoke test.",
            },
            {
                "case_id": "json_schema_vendor_readiness",
                "suite": "json_schema",
                "description": "Structured output schema reliability.",
            },
            {
                "case_id": "tool_call_web_and_ticket_plan",
                "suite": "tool_call",
                "description": "Native or fallback tool calling.",
            },
            {
                "case_id": "agent_mini_vendor_readiness",
                "suite": "agent_mini",
                "description": "5-10 step vendor integration readiness agent task.",
            },
        ],
    }


@app.post("/benchmarks/run", response_model=BenchmarkRunResponse)
def run_benchmark(
    request: BenchmarkRunRequest, db: Session = Depends(get_db)
) -> BenchmarkRunResponse:
    runner = BenchmarkRunner(get_settings(), db)
    return runner.run(request)


@app.get("/runs/{run_id}")
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = db.get(BenchmarkRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    results = db.execute(select(ModelResult).where(ModelResult.run_id == run_id)).scalars().all()
    return {
        "run": {
            "id": str(run.id),
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "suite": run.suite,
            "status": run.status,
            "summary": run.summary,
        },
        "results": [
            {
                "id": str(r.id),
                "model": r.model,
                "suite": r.suite,
                "case_id": r.case_id,
                "status": r.status,
                "score": r.score,
                "latency_ms_total": r.latency_ms_total,
                "error_type": r.error_type,
                "error_message": r.error_message,
                "raw_artifact_uri": r.raw_artifact_uri,
            }
            for r in results
        ],
    }


@app.post("/runs/{run_id}/export")
def export_run(run_id: UUID, db: Session = Depends(get_db)) -> dict:
    run = db.get(BenchmarkRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    payload = get_run(run_id, db)
    store = ArtifactStore(get_settings())
    json_uri = store.put_json(f"runs/{run_id}/exports/summary.json", payload)
    md = render_markdown_summary(payload)
    md_uri = store.put_text(f"runs/{run_id}/exports/summary.md", md, content_type="text/markdown")
    return {
        "run_id": str(run_id),
        "artifacts": [
            {"kind": "summary_json", "uri": json_uri},
            {"kind": "summary_md", "uri": md_uri},
        ],
    }


def render_markdown_summary(payload: dict) -> str:
    run = payload["run"]
    lines = [
        f"# Benchmark Run {run['id']}",
        "",
        f"Suite: `{run['suite']}`",
        f"Status: `{run['status']}`",
        "",
        "## Results",
        "",
    ]
    for r in payload.get("results", []):
        lines.append(
            f"- `{r['model']}` / `{r['case_id']}`: **{r['status']}**, score={r['score']}, latency={r['latency_ms_total']}ms"
        )
    return "\n".join(lines) + "\n"
