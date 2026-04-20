# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
# Copy both package files first for layer-cache efficiency
COPY frontend/package.json frontend/package-lock.json* ./
# Use clean install for deterministic, lock-file-driven builds
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Python Backend and serve
# Pin to a specific patch version for fully reproducible builds
FROM python:3.11.9-slim
WORKDIR /app

# Create non-root user (Cloud Run security best practice)
ENV PYTHONUNBUFFERED=1
RUN adduser --disabled-password --no-create-home appuser

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from Stage 1 into backend for static serving
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Switch to non-root user
USER appuser

# Expose port (Cloud Run sets the PORT env variable dynamically, default 8080)
ENV PORT="8080"
EXPOSE 8080

# Run uvicorn from inside /app/backend so that `from utils import ...` in
# main.py resolves to the sibling utils.py on sys.path. Running with the
# module path `backend.main:app` from /app would put /app on sys.path and
# fail to find utils.py at import time, causing the "failed to start" error.
CMD sh -c "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"

