FROM python:3.11-slim

# Install system dependencies for pyzbar, healthcheck, and opencv
RUN apt-get update && apt-get install -y \
    libzbar0 \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FastAPI on 8501 to match existing proxy
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/health || exit 1

ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8501"]
