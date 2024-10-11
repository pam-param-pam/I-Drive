# Stage 1: Build Node.js application
FROM node:latest as build

# Set working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json .
COPY package-lock.json .

# Install dependencies
RUN npm install

# Install another dependencie
RUN npm install sass-embedded-linux-arm64

# Copy the rest of the application code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Setup NGINX to serve the built app
FROM nginx:latest

# Create necessary directory for NGINX
RUN mkdir -p /var/www/idrive/frontend

# Copy built app from the 'build' stage
COPY --from=build /app/dist /var/www/idrive/frontend

# Copy nginx file
#COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 80 (default for HTTP)
EXPOSE 80

# Default command to run when container starts
CMD ["nginx", "-g", "daemon off;"]
