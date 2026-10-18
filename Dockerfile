FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --shell /bin/false --create-home app

WORKDIR /app

# Install build deps and python deps
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy app
COPY . /app

# Create dir for SQLite DB if used and set perms
RUN mkdir -p /data && chown -R app:app /data /app

EXPOSE ${PORT}

USER app

# Gunicorn will bind to the PORT env var. Use a small worker count suitable for lightweight deployments.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app", "--workers", "2", "--threads", "4", "--timeout", "30"]
