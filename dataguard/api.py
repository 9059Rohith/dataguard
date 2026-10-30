"""Operator API. Raw inputs and diagnostics require the same token as writes."""

import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from dataguard.service import Busy, Conflict, Pipeline


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=128)
    payload: dict


def authorize(authorization: str | None = Header(default=None)):
    configured = os.getenv("DATAGUARD_TOKEN", "")
    if len(configured.strip()) < 32:
        raise HTTPException(503, "Operator token is not configured (minimum 32 characters)")
    received = authorization.removeprefix("Bearer ") if authorization else ""
    if (
        not authorization
        or not authorization.startswith("Bearer ")
        or not secrets.compare_digest(received.encode(), configured.encode())
    ):
        raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})


def create_app(url=None):
    pipeline = Pipeline(url or os.getenv("DATABASE_URL", "sqlite:///dataguard.db"))
    registry = CollectorRegistry()
    counter = Counter(
        "dataguard_process_total", "Worker invocation outcomes", ["status"], registry=registry
    )
    latency = Histogram(
        "dataguard_process_seconds", "Validate/publication latency", registry=registry
    )
    db_up = Gauge("dataguard_database_up", "Database readiness", registry=registry)
    history = Gauge("dataguard_attempts", "Persisted attempt counts", ["status"], registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        if os.getenv("DATAGUARD_AUTO_INIT", "true").lower() == "true":
            pipeline.initialize()
        yield
        pipeline.engine.dispose()

    app = FastAPI(title="DataGuard", version="1.0.0", lifespan=lifespan)
    app.state.pipeline = pipeline

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 8_000_000):
            return JSONResponse({"detail": "Body exceeds 8 MB"}, status_code=413)
        # Enforce streamed bodies too; disconnecting clients are handled by ASGI server.
        if request.method in {"POST", "PUT", "PATCH"}:
            total = 0
            chunks = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > 8_000_000:
                    return JSONResponse({"detail": "Body exceeds 8 MB"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(KeyError)
    async def missing(_request, _error):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.exception_handler(Conflict)
    @app.exception_handler(Busy)
    async def conflict(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(SQLAlchemyError)
    async def unavailable(_request, _error):
        return JSONResponse({"detail": "Database unavailable"}, status_code=503)

    @app.get("/health")
    def health():
        return {"status": "alive"}

    @app.get("/ready")
    def ready():
        if not pipeline.ready():
            raise HTTPException(503, "Database schema is not initialized")
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics():
        try:
            db_up.set(int(pipeline.ready()))
            for status, count in pipeline.summary().items():
                history.labels(status).set(count)
        except SQLAlchemyError:
            db_up.set(0)
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get("/summary")
    def summary():
        return {"attempts": pipeline.summary(), "snapshots": pipeline.snapshots()}

    @app.get("/snapshots")
    def snapshots():
        return pipeline.snapshots()

    @app.get("/snapshots/{period}", dependencies=[Depends(authorize)])
    def current(period: str):
        return pipeline.current(period)

    @app.get("/quarantine", dependencies=[Depends(authorize)])
    def quarantine():
        return pipeline.quarantine()

    @app.get("/batches/{batch_id}", dependencies=[Depends(authorize)])
    def batch(batch_id: int):
        return pipeline.batch(batch_id)

    @app.post("/batches", status_code=201, dependencies=[Depends(authorize)])
    def stage(body: Submission):
        try:
            return {"batch_id": pipeline.stage(body.key, body.payload)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/batches/{batch_id}/run", dependencies=[Depends(authorize)])
    def run(batch_id: int):
        start = time.perf_counter()
        try:
            result = pipeline.process(batch_id)
            counter.labels(result["status"]).inc()
            return result
        except Exception:
            counter.labels("error").inc()
            raise
        finally:
            latency.observe(time.perf_counter() - start)

    @app.post("/recover", dependencies=[Depends(authorize)])
    def recover():
        return {"results": pipeline.recover()}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")

    @app.get("/dashboard.js")
    def script():
        return Response(
            Path(__file__).with_name("dashboard.js").read_text(encoding="utf-8"),
            media_type="text/javascript",
        )

    return app


app = create_app()
