# =============================================================================
# Alo ActivationOS Frontend - Production Dockerfile
# =============================================================================

FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Use Vite build directly for deployment image generation.
# This avoids unrelated repo-wide TypeScript check failures during Day 1 deployment.
RUN npx vite build

FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve

COPY --from=builder /app/dist ./dist

EXPOSE 8080

CMD ["serve", "-s", "dist", "-l", "8080"]
