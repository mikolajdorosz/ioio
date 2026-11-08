FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/var/lib/konwerter/converter.db \
    STORAGE_DIR=/var/lib/konwerter/storage \
    LOG_DIR=/var/log/konwerter

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/lib/konwerter/storage /var/log/konwerter \
    && chown -R appuser:appuser /var/lib/konwerter /var/log/konwerter

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8000/health').status == 200"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
