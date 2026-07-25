FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

COPY celery/ ./celery/

WORKDIR /app/celery

ENV PATH="/app/.venv/bin:$PATH"
ENV REDIS_URL=redis://redis:6379/0

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--autoscale=10,1"]
