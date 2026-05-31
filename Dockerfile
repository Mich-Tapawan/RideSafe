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
    && rm -rf /var/lib/apt/lists/*

ENV WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets PORT at runtime (default 10000)
EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 120 --access-logfile - app:app"]
