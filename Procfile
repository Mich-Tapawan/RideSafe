web: gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 90 --graceful-timeout 20 --max-requests 40 --max-requests-jitter 10 app:app
