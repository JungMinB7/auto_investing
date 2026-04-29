FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install uv

# Install production dependencies from pyproject.toml
# --no-build-isolation --no-project skips the local wheel build
COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "sqlalchemy>=2.0.30" \
    "alembic>=1.13.0" \
    "asyncpg>=0.29.0" \
    "redis>=5.0.0" \
    "httpx>=0.27.0" \
    "anthropic>=0.28.0" \
    "apscheduler>=3.10.4" \
    "dependency-injector>=4.41.0" \
    "structlog>=24.2.0" \
    "python-dotenv>=1.0.0" \
    "tenacity>=8.3.0"

COPY . .

# ── development target ─────────────────────────────────────
FROM base AS development
RUN uv pip install --system --no-cache \
    "pytest>=8.2.0" \
    "pytest-asyncio>=0.23.0" \
    "pytest-cov>=5.0.0" \
    "anyio>=4.4.0"

# ── production target ──────────────────────────────────────
FROM base AS production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
