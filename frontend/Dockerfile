# ----------------------------
# Stage 1: Build Node.js application
# ----------------------------
FROM node:20-slim AS build

# Set working directory
WORKDIR /app

# Copy only package files to leverage cache
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --ignore-scripts

# Optional: Install platform-specific dependency for ARM
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then npm install sass-embedded-linux-arm64; fi

# Copy app source code
COPY . .

# Build the app
RUN npm run build

# ----------------------------
# Stage 2: Serve with NGINX
# ----------------------------
FROM nginx:stable-alpine

# Create directory for built app
RUN mkdir -p /var/www/idrive/frontend

# Copy build output
COPY --from=build /app/dist /var/www/idrive/frontend

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy optional nginx config if you want custom behavior
# COPY nginx.conf /etc/nginx/nginx.conf

# Expose HTTP port
EXPOSE 80

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
