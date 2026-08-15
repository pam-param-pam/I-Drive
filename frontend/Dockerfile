# Stage 1: Build Node.js application
ARG BACKEND_IMAGE=ghcr.io/pam-param-pam/idrive-backend:latest
FROM node:latest AS builder

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY frontend/package.json .
COPY frontend/package-lock.json .

# Install dependencies
RUN npm install

# Install platform-specific dependency for ARM
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then npm install sass-embedded-linux-arm64; fi

# Copy the rest of the application code
COPY frontend/ .

# Build the application
RUN npm run build

# Use the backend image as the source for collected Django static files.
FROM ${BACKEND_IMAGE} AS backend_static

# Stage 2: Setup NGINX to serve the built app
FROM nginx:latest

# Create necessary directory for NGINX
RUN mkdir -p /var/www/idrive/frontend

# Copy built app from the 'builder' stage
COPY --from=builder /app/dist /var/www/idrive/frontend

# Copy the entrypoint script
COPY frontend/entrypoint.sh /entrypoint.sh

# Copy Django static files from the backend image.
COPY --from=backend_static /var/www/idrive/backend-static/ /var/www/idrive/backend-static/

# Bake the NGINX configuration and auth handler into the image.
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/auth.js /etc/nginx/auth.js

RUN chmod +x /entrypoint.sh

RUN apt-get update && \
    apt-get install -y nginx-module-njs && \
    rm -rf /var/lib/apt/lists/*

# Expose port 80 (default for HTTP)
EXPOSE 80

# Default command to run when container starts
ENTRYPOINT ["./entrypoint.sh"]
