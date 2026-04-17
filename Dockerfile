# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
# Copy both package files first
COPY frontend/package.json frontend/package-lock.json* ./
# Use clean install for deterministic builds
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Python Backend and serve
FROM python:3.11-slim
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from Stage 1 into backend for static serving
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Expose port 8080 (Cloud Run default)
ENV PORT="8080"
EXPOSE 8080

# Run uvicorn natively on Cloud Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
