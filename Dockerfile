# syntax=docker/dockerfile:1

FROM node:24-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM dependencies AS app-base

RUN groupadd --gid 10001 devgpt \
    && useradd --uid 10001 --gid devgpt --create-home --shell /usr/sbin/nologin devgpt

COPY --chown=devgpt:devgpt backend/ /app/backend/
COPY --from=frontend-build --chown=devgpt:devgpt /app/frontend/dist/ /app/frontend/dist/

RUN mkdir -p /app/backend/uploads && chown -R devgpt:devgpt /app/backend/uploads

EXPOSE 8080


FROM app-base AS test

USER root
RUN pip install -r requirements-dev.txt
USER devgpt

CMD ["pytest", "-q", "-o", "cache_dir=/tmp/pytest_cache"]


FROM app-base AS runtime

USER devgpt

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/openapi.json', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
