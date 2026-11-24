# Vite dev server for the frontend Compose service (build context: ./frontend).
FROM node:22-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 2026
CMD ["npm", "start"]
