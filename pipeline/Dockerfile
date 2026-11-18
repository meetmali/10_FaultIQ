# FaultIQ pipeline worker image.
FROM python:3.13.18-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY faultiq ./faultiq
COPY worker ./worker
RUN uv sync --frozen --no-dev

# UID 1654 matches the 'app' user in the .NET chiseled image, so both can write the shared volume.
RUN useradd --create-home --uid 1654 faultiq \
    && mkdir -p /app/data/uploads \
    && chown -R faultiq:faultiq /app/data
USER faultiq

CMD ["python", "-m", "worker"]
