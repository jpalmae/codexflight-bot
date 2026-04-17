FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /data && \
    useradd -r -u 1000 bot && \
    chown -R bot:bot /data /app

USER bot

CMD ["python", "-m", "app.main"]
