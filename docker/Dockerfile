FROM python:3.12-slim

WORKDIR /app

# Install system utilities for IPC / network troubleshooting
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source tree
COPY . .

ENV PYTHONUNBUFFERED=1
ENV NEXUS_BIND=0.0.0.0

EXPOSE 9000 9001 8080

CMD ["python", "app.py"]
