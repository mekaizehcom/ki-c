FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS dev
ENV TESSA_ENV=development
CMD ["python", "-m", "worker.main"]

FROM base AS prod
ENV TESSA_ENV=production
COPY worker /srv/worker
CMD ["python", "-m", "worker.main"]
