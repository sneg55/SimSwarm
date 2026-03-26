# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim AS backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy backend code
COPY saas/ ./saas/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY infra/ ./infra/
COPY demos/ ./demos/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8080

CMD ["uvicorn", "saas.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
