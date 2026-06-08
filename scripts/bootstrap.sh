#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/idrive-app}"
BASE_URL="https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master"
POSTGRES_VOLUME="idrive-app_postgres_data"

BACKEND_CONTAINER="idrive-backend"
TIMEOUT_SECONDS=120

IS_DEV_ENV="${1:-false}"
IS_DEV_ENV="$(echo "$IS_DEV_ENV" | tr '[:upper:]' '[:lower:]')"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

download_file() {
  local url="$1"
  local target="$2"
  local tmp

  tmp="$(mktemp)"
  curl -fsSL "$url" -o "$tmp"
  mv "$tmp" "$target"
}

if [ "$IS_DEV_ENV" != "true" ] && [ "$IS_DEV_ENV" != "false" ]; then
  fail "IS_DEV_ENV must be either 'true' or 'false'."
fi

echo "Running from: $(pwd)"
echo "Checking prerequisites..."

require_cmd curl
require_cmd docker
require_cmd openssl
require_cmd mktemp
require_cmd date

docker info >/dev/null 2>&1 || fail "Docker daemon is not running or is not accessible"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not available"

if [ -e "$APP_DIR" ]; then
  echo "Found existing path:"
  fail "'$APP_DIR' already exists. Refusing to continue."
fi

if docker volume inspect "$POSTGRES_VOLUME" >/dev/null 2>&1; then
  fail "Docker volume '$POSTGRES_VOLUME' already exists. Refusing to reuse an existing database volume."
fi

if docker inspect "$BACKEND_CONTAINER" >/dev/null 2>&1; then
  fail "Container '$BACKEND_CONTAINER' already exists. Remove the old container before running this script."
fi

echo "Creating application directory..."
mkdir "$APP_DIR"
cd "$APP_DIR"

mkdir -p nginx

echo "Downloading configuration files..."
download_file "$BASE_URL/docker-compose.yml" docker-compose.yml
download_file "$BASE_URL/nginx/nginx.conf" nginx/nginx.conf
download_file "$BASE_URL/nginx/auth.js" nginx/auth.js

echo "Generating .env..."

cat > .env <<EOF
# never run with true in PROD
IS_DEV_ENV=${IS_DEV_ENV}

# http or https
PROTOCOL=http

# deploy host
DEPLOYMENT_HOST=localhost

# external backend port
BACKEND_PORT=8000

# entrypoint port for the entire application
NGINX_PORT=80

POSTGRES_VOLUME=${POSTGRES_VOLUME}
POSTGRES_USER=idrive
POSTGRES_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
BACKEND_SECRET_KEY=$(openssl rand -hex 64)
SIGNING_SECRET=$(openssl rand -hex 64)
EOF

chmod 600 .env

echo
echo "Starting containers..."
docker compose up -d

echo
echo "Waiting for backend container to appear..."

until docker inspect "$BACKEND_CONTAINER" >/dev/null 2>&1; do
  sleep 1
done

echo "Backend container exists. Waiting until it is ready..."

START_TIME=$(date +%s)

while true; do
  STATUS=$(docker inspect -f '{{.State.Status}}' "$BACKEND_CONTAINER" 2>/dev/null || echo "missing")
  HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$BACKEND_CONTAINER" 2>/dev/null || echo "missing")

  if [ "$STATUS" = "exited" ] || [ "$STATUS" = "dead" ]; then
    echo "ERROR: Backend container failed. Status: $STATUS"
    docker logs "$BACKEND_CONTAINER" --tail=100 || true
    exit 1
  fi

  if [ "$HEALTH" = "unhealthy" ]; then
    echo "ERROR: Backend container is unhealthy."
    docker logs "$BACKEND_CONTAINER" --tail=100 || true
    exit 1
  fi

  if docker exec "$BACKEND_CONTAINER" python manage.py check >/dev/null 2>&1; then
    echo "Backend is ready."
    break
  fi

  NOW=$(date +%s)
  ELAPSED=$((NOW - START_TIME))

  if [ "$ELAPSED" -ge "$TIMEOUT_SECONDS" ]; then
    echo "ERROR: Backend did not become ready within ${TIMEOUT_SECONDS} seconds."
    echo "Container status: $STATUS"
    echo "Health status: $HEALTH"
    docker logs "$BACKEND_CONTAINER" --tail=100 || true
    exit 1
  fi

  echo "Backend not ready yet... ${ELAPSED}s/${TIMEOUT_SECONDS}s"
  sleep 2
done

echo
echo "Running database migrations..."
docker exec "$BACKEND_CONTAINER" python manage.py migrate

echo
echo "Creating admin user..."

if [ ! -t 0 ]; then
  fail "This script needs an interactive terminal to create the admin user."
fi

docker exec -it "$BACKEND_CONTAINER" python manage.py createuser --staff </dev/tty

echo
if [ "$IS_DEV_ENV" = "true" ]; then
  echo "You are running in DEVELOPMENT MODE. Running with IS_DEV_ENV=True in PROD is a security risk!"
fi
echo "Setup complete."
echo "Open in browser:"
echo "http://localhost"