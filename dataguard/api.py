"""Operator API. Raw inputs and diagnostics require the same token as writes."""

import base64
import hashlib
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import anyio
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi import Path as PathParameter
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from dataguard.guard import RequestGuard
from dataguard.service import Busy, Conflict, Pipeline

BatchId = Annotated[int, PathParameter(ge=1, le=2_147_483_647)]

DEFAULT_CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
DOCUMENTATION_ASSETS = {
    "/docs": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
    "/redoc": "https://cdn.jsdelivr.net/npm/redoc@2/",
    "/docs/oauth2-redirect": "",
}


def documentation_csp(body: bytes, path: str) -> str:
    """Hash only server-generated documentation bootstrap scripts, never arbitrary inline JS."""
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", body.decode(), flags=re.DOTALL)
    hashes = " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()}'"
        for script in scripts
        if script.strip()
    )
    assets = DOCUMENTATION_ASSETS[path]
    redoc_fonts = " https://fonts.googleapis.com" if path == "/redoc" else ""
    redoc_workers = "; worker-src 'self' blob:" if path == "/redoc" else ""
    redoc_logo = " https://cdn.redoc.ly/redoc/logo-mini.svg" if path == "/redoc" else ""
    return (
        f"default-src 'self'; script-src 'self' {assets} {hashes}; "
        f"style-src 'self' 'unsafe-inline' {assets}{redoc_fonts}; "
        f"img-src 'self' data: https://fastapi.tiangolo.com/img/favicon.png{redoc_logo}; "
        "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; "
        f"object-src 'none'; base-uri 'none'; frame-ancestors 'none'{redoc_workers}"
    )


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


def public_demo_enabled():
    return os.getenv("DATAGUARD_PUBLIC_DEMO", "").lower() == "true"


def metadata_access(authorization: str | None = Header(default=None)):
    if not public_demo_enabled():
        authorize(authorization)


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
        if os.getenv("DATAGUARD_SEED_DEMO", "").lower() == "true":
            from dataguard.demo import seed_synthetic_demo

            seed_synthetic_demo(pipeline)
        yield
        pipeline.engine.dispose()

    app = FastAPI(
        title="DataGuard",
        version="1.0.0",
        lifespan=lifespan,
        swagger_ui_parameters={"validatorUrl": None},
    )
    app.state.pipeline = pipeline
    app.state.request_limiter = anyio.CapacityLimiter(4)
    app.state.body_timeout_seconds = 10.0

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        response = await call_next(request)
        # Built-in docs are small HTML responses. Buffer only these exact
        # routes so their real bootstrap bytes can be authorized by CSP hashes.
        route_path = request.scope["path"].removeprefix(request.scope.get("root_path", ""))
        csp = DEFAULT_CSP
        if route_path in DOCUMENTATION_ASSETS and response.headers.get(
            "content-type", ""
        ).startswith("text/html"):
            body = b"".join([chunk async for chunk in response.body_iterator])
            csp = documentation_csp(body, route_path)
            response = Response(
                body,
                status_code=response.status_code,
                headers=dict(response.headers),
                background=response.background,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = csp
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

    @app.get("/metrics", dependencies=[Depends(authorize)])
    def metrics():
        try:
            db_up.set(int(pipeline.ready()))
            for status, count in pipeline.summary().items():
                history.labels(status).set(count)
        except SQLAlchemyError:
            db_up.set(0)
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.get("/summary", dependencies=[Depends(metadata_access)])
    def summary():
        return {
            "public_demo": public_demo_enabled(),
            "attempts": pipeline.summary(),
            "snapshots": pipeline.snapshots(),
        }

    @app.get("/snapshots", dependencies=[Depends(metadata_access)])
    def snapshots():
        return pipeline.snapshots()

    @app.get("/snapshots/{period}", dependencies=[Depends(authorize)])
    def current(period: str):
        return pipeline.current(period)

    @app.get("/quarantine", dependencies=[Depends(authorize)])
    def quarantine():
        return pipeline.quarantine()

    @app.get("/batches/{batch_id}", dependencies=[Depends(authorize)])
    def batch(batch_id: BatchId):
        return pipeline.batch(batch_id)

    @app.post("/batches", status_code=201, dependencies=[Depends(authorize)])
    def stage(body: Submission):
        try:
            return {"batch_id": pipeline.stage(body.key, body.payload)}
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/batches/{batch_id}/run", dependencies=[Depends(authorize)])
    def run(batch_id: BatchId):
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

    app.add_middleware(RequestGuard, state=app.state, authorize=authorize, default_csp=DEFAULT_CSP)
    return app


app = create_app()
