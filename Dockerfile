FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for any source packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user.
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY config ./config
COPY knowledge_base ./knowledge_base
COPY frontend ./frontend
COPY pyproject.toml .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
