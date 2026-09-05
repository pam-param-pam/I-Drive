# syntax=docker/dockerfile:1.7

# Stage 1: Build Node.js application
ARG BACKEND_IMAGE=ghcr.io/pam-param-pam/idrive-backend:latest
FROM node:latest AS builder

# Set working directory
WORKDIR /app

# Copy dependency manifests before application source so source changes do not
# invalidate the dependency-install layer.
COPY package.json package-lock.json ./

# Install the exact locked dependency tree and reuse npm's download cache.
RUN --mount=type=cache,target=/root/.npm npm ci

# Install platform-specific dependency for ARM
ARG TARGETARCH
RUN --mount=type=cache,target=/root/.npm \
    if [ "$TARGETARCH" = "arm64" ]; then npm install sass-embedded-linux-arm64; fi

# Copy the rest of the application code
COPY . .

# Build the application
RUN npm run build

# Use the backend image as the source for collected Django static files.
FROM ${BACKEND_IMAGE} AS backend_static

# Stage 2: Setup NGINX to serve the built app
FROM nginx:latest

# Copy built app from the 'builder' stage
COPY --from=builder /app/dist /var/www/idrive/frontend

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh

# Copy Django static files from the backend image.
COPY --from=backend_static /var/www/idrive/backend-static/ /var/www/idrive/backend-static/

# Bake the NGINX configuration and auth handler into the image.
COPY --from=nginx-config nginx.conf /etc/nginx/nginx.conf
COPY --from=nginx-config auth.js /etc/nginx/auth.js

RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

RUN apt-get update && \
    apt-get install -y nginx-module-njs && \
    rm -rf /var/lib/apt/lists/*

# Expose port 80 (default for HTTP)
EXPOSE 80

# Default command to run when container starts
ENTRYPOINT ["/entrypoint.sh"]
