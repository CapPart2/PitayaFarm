# Build the mobile/web interface, then package it with both Flask APIs.
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx gettext-base libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . ./
COPY --from=frontend-build /frontend/dist /app/frontend/dist

RUN chmod +x /app/deploy/start.sh
EXPOSE 8080
CMD ["/app/deploy/start.sh"]
