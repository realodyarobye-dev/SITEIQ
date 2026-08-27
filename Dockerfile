FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py
COPY siteiq ./siteiq

RUN test -f /app/siteiq/web/templates/home.html \
    && test -f /app/siteiq/web/templates/error.html \
    && test -d /app/siteiq/web/static

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 8 --timeout 180 --graceful-timeout 30 --access-logfile - --error-logfile -"]
