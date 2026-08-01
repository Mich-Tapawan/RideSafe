FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps: wkhtmltopdf (PDF), GDAL/GEOS (geopandas), fonts for chart/PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    gcc \
    g++ \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV WEB_CONCURRENCY=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

# Bind immediately so Render's port scan succeeds. Seed + RAG run inside app import.
# timeout 90 < typical free-proxy limits; max-requests recycles memory after chat spikes.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-1} --threads 1 --timeout ${GUNICORN_TIMEOUT:-90} --graceful-timeout 20 --max-requests ${GUNICORN_MAX_REQUESTS:-40} --max-requests-jitter 10 --access-logfile - app:app"]
