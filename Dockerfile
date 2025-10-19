FROM python:3.10-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser requirements.txt /app/

RUN mkdir -p /home/appuser/.streamlit && \
    echo '[server]' > /home/appuser/.streamlit/config.toml && \
    echo 'port = 8501' >> /home/appuser/.streamlit/config.toml && \
    echo 'address = "0.0.0.0"' >> /home/appuser/.streamlit/config.toml && \
    echo 'headless = true' >> /home/appuser/.streamlit/config.toml && \
    chown -R appuser:appuser /home/appuser/.streamlit

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

USER appuser

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "src/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.serverAddress=localhost", \
     "--browser.serverPort=8501"]