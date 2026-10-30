FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY dataguard /app/dataguard
# Source module runs from /app; build tools never enter the runtime image.
RUN useradd --uid 10001 --create-home app && mkdir /data && chown app:app /data
USER 10001:10001
ENV DATAGUARD_AUTO_INIT=false
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]
CMD ["python", "-m", "dataguard.entrypoint"]
