FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
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

COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 4177
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s CMD curl -f http://127.0.0.1:4177/api/health || exit 1
CMD ["python", "-m", "uvicorn", "live_demo.server:app", "--host", "0.0.0.0", "--port", "4177"]
