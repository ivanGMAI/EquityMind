# syntax=docker/dockerfile:1

# =============================================================================
# EquityMind frontend — React (Vite) built to static files, served by nginx.
# nginx also proxies /api/* to the FastAPI service (see nginx.conf).
# =============================================================================

# ---- Stage 1: build the static bundle ---------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first so source edits don't invalidate the npm cache.
COPY package*.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ---- Stage 2: nginx runtime --------------------------------------------------
FROM nginx:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
