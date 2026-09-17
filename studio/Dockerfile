FROM python:3.12-slim

WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --index-url "$PIP_INDEX_URL" \
    --trusted-host "$PIP_TRUSTED_HOST" \
    --trusted-host files.pythonhosted.org \
    --trusted-host packagefeedproxy.microsoft.io \
    -r requirements.txt
COPY catalog.py server.py ./
COPY static ./static
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
