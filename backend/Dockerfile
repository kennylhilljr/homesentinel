# Build context: repository root (see docker-compose.yml).
# Stage 1 builds the dashboard; stage 2 serves it from the backend over HTTPS.
FROM node:22-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
# curl: health check. arp-scan, nmap, net-tools (arp): device discovery.
# iputils-ping: home-network check that gates polling. lsof: local service monitor.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl arp-scan nmap net-tools iputils-ping lsof \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
# main.py serves the dashboard from ../frontend/build relative to the backend dir.
COPY --from=frontend /src/frontend/build /app/frontend/build
ENV PYTHONUNBUFFERED=1
EXPOSE 8443
CMD ["python", "main.py"]
