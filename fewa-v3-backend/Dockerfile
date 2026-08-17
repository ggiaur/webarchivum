FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (including docker CLI for crawling worker)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY fewa-v3-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy spec, fewa-automation and backend code into /app
COPY spec /app/spec
COPY fewa-automation /app/fewa-automation
COPY fewa-v3-backend /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
