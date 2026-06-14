#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/idrive-app"
BASE_URL="https://raw.githubusercontent.com/pam-param-pam/I-Drive/refs/heads/master"
POSTGRES_VOLUME="idrive-app_postgres_data"

BACKEND_CONTAINER="idrive-backend"
NGINX_CONTAINER="idrive-nginx"

TIMEOUT_SECONDS=120

IS_DEV_ENV="true"
PROTOCOL="http"
DEPLOYMENT_HOST="localhost"
PORT="80"
BACKEND_PORT="8000"

ADMIN_LOGIN="admin"
ADMIN_PASSWORD="admin"

CONFIG_FILE_SOURCE=""
CONFIG_FILE_NAME="config.override.json"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage:
  $0 [options]

Options:
  --dev true|false             Run in development mode. Default: ${IS_DEV_ENV}
  --protocol http|https        External protocol. Default: ${PROTOCOL}
  --deployment-host HOST       Deployment host without protocol. Default: ${DEPLOYMENT_HOST}
  --port PORT                  Public Nginx/application port. Default: ${PORT}
  --backend-port PORT          External backend port. Default: ${BACKEND_PORT}
  --app-dir PATH               Application directory. Default: ${APP_DIR}
  --config-file PATH           Optional config override file. If omitted, an empty override file is created.
  --admin-login LOGIN          Admin user login. Default: ${ADMIN_LOGIN}
  --admin-password PASSWORD    Admin user password. Default: ${ADMIN_PASSWORD}
  -h, --help                   Show this help

Example:
  $0 --dev ${IS_DEV_ENV} --protocol ${PROTOCOL} --deployment-host ${DEPLOYMENT_HOST} --port ${PORT} --backend-port ${BACKEND_PORT} --config-file ./config.override.json --admin-login ${ADMIN_LOGIN} --admin-password '<password>'
EOF
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

normalize_bool() {
  local value
  value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"

  case "$value" in
    true|false) echo "$value" ;;
    *) fail "$2 must be either 'true' or 'false'." ;;
  esac
}

validate_port() {
  local name="$1"
  local value="$2"

  [[ "$value" =~ ^[0-9]+$ ]] || fail "$name must be a number."
  [ "$value" -ge 1 ] && [ "$value" -le 65535 ] || fail "$name must be between 1 and 65535."
}

validate_non_empty() {
  local name="$1"
  local value="$2"

  [ -n "$value" ] || fail "$name cannot be empty."
}

validate_deployment_host() {
  local value="$1"

  validate_non_empty "--deployment-host" "$value"

  case "$value" in
    http://*|https://*)
      fail "--deployment-host must not include protocol. Use 'example.com', not '${value}'."
      ;;
  esac

  case "$value" in
    */*)
      fail "--deployment-host must not contain a path. Use 'example.com', not '${value}'."
      ;;
  esac

  [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]] || fail "--deployment-host contains invalid characters."
}

validate_config_file_path() {
  local path="$1"

  validate_non_empty "--config-file" "$path"
  [ -e "$path" ] || fail "Config file does not exist: $path"
  [ -f "$path" ] || fail "Config path is not a regular file: $path"
  [ -r "$path" ] || fail "Config file is not readable: $path"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dev)
      [ "$#" -ge 2 ] || fail "--dev requires a value: true or false."
      IS_DEV_ENV="$(normalize_bool "$2" "--dev")"
      shift 2
      ;;
    --protocol)
      [ "$#" -ge 2 ] || fail "--protocol requires a value: http or https."
      PROTOCOL="$(echo "$2" | tr '[:upper:]' '[:lower:]')"
      [ "$PROTOCOL" = "http" ] || [ "$PROTOCOL" = "https" ] || fail "--protocol must be either 'http' or 'https'."
      shift 2
      ;;
    --deployment-host)
      [ "$#" -ge 2 ] || fail "--deployment-host requires a value."
      DEPLOYMENT_HOST="$2"
      validate_deployment_host "$DEPLOYMENT_HOST"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || fail "--port requires a value."
      PORT="$2"
      validate_port "--port" "$PORT"
      shift 2
      ;;
    --backend-port)
      [ "$#" -ge 2 ] || fail "--backend-port requires a value."
      BACKEND_PORT="$2"
      validate_port "--backend-port" "$BACKEND_PORT"
      shift 2
      ;;
    --app-dir)
      [ "$#" -ge 2 ] || fail "--app-dir requires a value."
      APP_DIR="$2"
      validate_non_empty "--app-dir" "$APP_DIR"
      shift 2
      ;;
    --config-file)
      [ "$#" -ge 2 ] || fail "--config-file requires a value."
      CONFIG_FILE_SOURCE="$2"
      validate_config_file_path "$CONFIG_FILE_SOURCE"
      shift 2
      ;;
    --admin-login)
      [ "$#" -ge 2 ] || fail "--admin-login requires a value."
      ADMIN_LOGIN="$2"
      validate_non_empty "--admin-login" "$ADMIN_LOGIN"
      shift 2
      ;;
    --admin-password)
      [ "$#" -ge 2 ] || fail "--admin-password requires a value."
      ADMIN_PASSWORD="$2"
      validate_non_empty "--admin-password" "$ADMIN_PASSWORD"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1. Use --help for usage."
      ;;
  esac
done

validate_non_empty "ADMIN_LOGIN" "$ADMIN_LOGIN"
validate_non_empty "ADMIN_PASSWORD" "$ADMIN_PASSWORD"
validate_deployment_host "$DEPLOYMENT_HOST"

echo "Running from: $(pwd)"
echo "Checking prerequisites..."

require_cmd curl
require_cmd docker
require_cmd openssl
require_cmd mktemp
require_cmd date

docker info >/dev/null 2>&1 || fail "Docker daemon is not running or is not accessible."
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not available."

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

if docker inspect "$NGINX_CONTAINER" >/dev/null 2>&1; then
  fail "Container '$NGINX_CONTAINER' already exists. Remove the old container before running this script."
fi

echo "Creating application directory..."
mkdir "$APP_DIR"
cd "$APP_DIR"

mkdir -p nginx

echo "Downloading configuration files..."
download_file "$BASE_URL/docker-compose.yml" docker-compose.yml
download_file "$BASE_URL/nginx/nginx.conf" nginx/nginx.conf
download_file "$BASE_URL/nginx/auth.js" nginx/auth.js

echo "Preparing config override file..."

if [ -n "$CONFIG_FILE_SOURCE" ]; then
  cp "$CONFIG_FILE_SOURCE" "$CONFIG_FILE_NAME"
else
  echo "{}" > "$CONFIG_FILE_NAME"
fi

chmod 600 "$CONFIG_FILE_NAME"

echo "Generating .env..."

cat > .env <<EOF
# never run with true in PROD
IS_DEV_ENV=${IS_DEV_ENV}

# http or https
PROTOCOL=${PROTOCOL}

# deploy host, without http:// or https://
DEPLOYMENT_HOST=${DEPLOYMENT_HOST}

# external backend port
BACKEND_PORT=${BACKEND_PORT}

# entrypoint port for the entire application
NGINX_PORT=${PORT}

# backend config override file inside container
IDRIVE_CONFIG_FILE=/config/config.override.json

POSTGRES_VOLUME=${POSTGRES_VOLUME}
POSTGRES_USER=idrive
POSTGRES_PASSWORD=$(openssl rand -hex 32)
REDIS_PASSWORD=$(openssl rand -hex 32)
BACKEND_SECRET_KEY=$(openssl rand -hex 64)
SIGNING_SECRET=$(openssl rand -hex 64)
EOF

chmod 600 .env

echo
echo "Configuration:"
echo "  APP_DIR:          $APP_DIR"
echo "  IS_DEV_ENV:       $IS_DEV_ENV"
echo "  PROTOCOL:         $PROTOCOL"
echo "  DEPLOYMENT_HOST:  $DEPLOYMENT_HOST"
echo "  PORT:             $PORT"
echo "  BACKEND_PORT:     $BACKEND_PORT"
echo "  CONFIG_FILE:      $APP_DIR/$CONFIG_FILE_NAME"
echo "  ADMIN_LOGIN:      $ADMIN_LOGIN"
echo "  ADMIN_PASSWORD:   $ADMIN_PASSWORD"
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
docker exec "$BACKEND_CONTAINER" python manage.py createuser --staff --login "$ADMIN_LOGIN" --password "$ADMIN_PASSWORD"

echo

if [ "$IS_DEV_ENV" = "true" ]; then
  echo "WARNING: You are running in DEVELOPMENT MODE. Running with IS_DEV_ENV=true in production is a security risk."
fi

if [ "$ADMIN_LOGIN" = "admin" ] && [ "$ADMIN_PASSWORD" = "admin" ]; then
  echo "WARNING: Default admin credentials are being used. Change them after setup."
fi

echo "Setup complete."
echo "Open in browser:"
echo "${PROTOCOL}://${DEPLOYMENT_HOST}:${PORT}"