FROM node:24-alpine AS web-build

WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Install system dependencies for pyzbar, healthcheck, and opencv.
RUN apt-get update && apt-get install -y \
    libzbar0 \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir playwright-stealth

COPY src/ ./
RUN chmod +x /app/docker-entrypoint.sh
COPY --from=web-build /web/dist /app/web_dist

# FastAPI on 8501 to match existing proxy
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/api/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
