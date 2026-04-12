FROM python:3.11-slim AS base

WORKDIR /app

# System deps for pybaseball/numpy/scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir anthropic gunicorn

COPY . .

# Create dirs for model persistence and SQLite
RUN mkdir -p /app/models /app/data

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////app/data/cubsedge.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); assert r.status_code==200"

# Default: run the API server
CMD ["gunicorn", "app.main:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
