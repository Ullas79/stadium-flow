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

# Set working directory to backend so `uvicorn main:app` finds `utils.py`
WORKDIR /app/backend

# Switch to non-root user
USER appuser

# Expose port (Cloud Run sets the PORT env variable dynamically, default 8080)
ENV PORT="8080"
EXPOSE 8080

# Run uvicorn using exec form to properly handle OS signals and port mapping
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

