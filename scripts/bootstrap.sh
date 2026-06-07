#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master"

echo "Creating directories..."
mkdir -p nginx

echo "Downloading docker-compose.yml..."
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

echo "Downloading nginx/nginx.conf..."
curl -fsSL "$BASE_URL/nginx/nginx.conf" -o nginx/nginx.conf

if [ -f .env ]; then
  echo ".env already exists - leaving it unchanged"
else
  echo "Generating .env..."

  cat > .env <<EOF
# never run with true in PROD
IS_DEV_ENV=false

# http or https
PROTOCOL=http

# deploy host
DEPLOYMENT_HOST=localhost

# external backend port
BACKEND_PORT=8000

# entrypoint port for the entire application
NGINX_PORT=80

POSTGRES_VOLUME=postgres_data
POSTGRES_USER=idrive
POSTGRES_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
BACKEND_SECRET_KEY=$(openssl rand -hex 64)
SIGNING_SECRET=$(openssl rand -hex 64)
EOF

  chmod 600 .env
  echo "Generated .env"
fi

echo
echo "Bootstrap complete."
echo "Now run:"
echo "docker compose up"