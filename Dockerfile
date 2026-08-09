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

# Bind fast for Render deploy health checks. max-requests 0 = no worker recycle (avoids
# re-running heavy import warmup on free tier). Set GUNICORN_MAX_REQUESTS>0 to re-enable.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-1} --threads 1 --timeout ${GUNICORN_TIMEOUT:-90} --graceful-timeout 20 --max-requests ${GUNICORN_MAX_REQUESTS:-0} --access-logfile - app:app"]
