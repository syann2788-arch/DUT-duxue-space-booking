FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY init_reference_data.py create_admin.py import_counselors.py ./
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /app/uploads /app/private_uploads /app/credentials \
    && chown -R app:app /app \
    && chmod 700 /app/credentials
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
