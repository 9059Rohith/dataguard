ARG BUILDER_IMAGE=cgr.dev/chainguard/python:latest-dev@sha256:95d8cc85fad8acc8ebad357e1972f2a975c498a65406cd9b00bb2233371a94a2
ARG RUNTIME_IMAGE=cgr.dev/chainguard/python:latest@sha256:bf06e09413bec94d6489f0be783b8f9349339907b89e0f759d190d0b95ab2d8f
FROM ${BUILDER_IMAGE} AS build
USER 0
WORKDIR /app
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install pip==26.2.2 \
    && /opt/venv/bin/python -m pip install --only-binary=:all: -r requirements.lock
COPY pyproject.toml ./
COPY dataguard ./dataguard
RUN --mount=type=cache,target=/root/.cache/pip /opt/venv/bin/python -m pip install --no-deps . \
    && mkdir /data && chown 10001:10001 /data \
    && /opt/venv/bin/python -m pip uninstall -y pip setuptools wheel

FROM build AS verify
COPY requirements-ci.lock requirements-dev.lock ./
# PyYAML has no CPython 3.15 wheel; build its supported pure-Python implementation.
# --no-deps keeps production packages in /opt/venv authoritative.
RUN --mount=type=cache,target=/root/.cache/pip PYYAML_FORCE_LIBYAML=0 python -m pip install \
    --target /test-tools --no-deps --only-binary=:all: --no-binary=pyyaml -r requirements-ci.lock
COPY tests ./tests
COPY scripts/verify_build.py ./scripts/verify_build.py
COPY dags ./dags
COPY docs/schemas ./docs/schemas
COPY Dockerfile ./
RUN --network=none PYTHONPATH=/test-tools:/app /opt/venv/bin/python scripts/verify_build.py /verification/receipt.json

FROM ${RUNTIME_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:/usr/bin DATAGUARD_AUTO_INIT=false
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=10001:10001 /data /data
COPY --from=verify /verification/receipt.json /app/build-verification.json
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=25s CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/ready', timeout=22)"]
ENTRYPOINT []
CMD ["python", "-m", "dataguard.entrypoint"]
