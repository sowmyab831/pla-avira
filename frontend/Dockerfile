# Multi-stage build for React + Vite + Nginx
ARG TARGETARCH
ARG BUILD_DATE
ARG CACHE_BUST
FROM --platform=linux/${TARGETARCH:-amd64} node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY --chown=node:node . .

# Build application
RUN npm run build

# Final stage: Nginx
ARG TARGETARCH
FROM --platform=linux/${TARGETARCH:-amd64} nginx:alpine

# Copy built app to Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
