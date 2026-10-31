FROM node:22-slim AS web
WORKDIR /w
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=web /w/dist ./static
ARG GIT_REVISION=unknown
ENV GIT_REVISION=$GIT_REVISION ENVIRONMENT=production
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed_if_empty && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
