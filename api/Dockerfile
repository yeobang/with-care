# with-care API (P11 배포) — Fly.io
FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
