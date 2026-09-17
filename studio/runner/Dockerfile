FROM python:3.12-slim

WORKDIR /control
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org
RUN pip install --no-cache-dir \
    --index-url "$PIP_INDEX_URL" \
    --trusted-host "$PIP_TRUSTED_HOST" \
    --trusted-host files.pythonhosted.org \
    --trusted-host packagefeedproxy.microsoft.io \
    -r requirements.txt
COPY server.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8500 8501
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8500"]
