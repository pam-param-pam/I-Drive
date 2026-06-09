#!/usr/bin/env bash
set -euo pipefail

PYTHON_CMD=""

REPO_URL="https://github.com/pam-param-pam/I-Drive"
DEV_DIR="idrive-dev"

EXPECTED_PYTHON_MAJOR="3"
EXPECTED_PYTHON_MINOR="12"
EXPECTED_PYTHON_VERSION="${EXPECTED_PYTHON_MAJOR}.${EXPECTED_PYTHON_MINOR}"

EXPECTED_NODE_MAJOR="20"
EXPECTED_NODE_VERSION="v24.15.0"

SIGNING_SECRET="very_secret_signing_key"
BACKEND_SECRET_KEY="very_secret_backend_key"

REDIS_CONTAINER="dev_idrive_redis"
POSTGRES_CONTAINER="dev_idrive_postgres"
POSTGRES_VOLUME="dev_idrive_postgres_data"

REDIS_PASSWORD="1234"

POSTGRES_DB="dev_idrive_postgres"
POSTGRES_USER="admin"
POSTGRES_PASSWORD="1234"

FRONTEND_PORT="5173"
BACKEND_PORT="8000"

ADMIN_LOGIN="admin"
ADMIN_PASSWORD="admin"
DEPLOYMENT_HOST="localhost"
IS_DEV_ENV="True"
NGINX_PORT="80"
POSTGRES_PORT="5432"
REDIS_PORT="6379"
PROTOCOL="http"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage:
  $0 [options]

Options:
  --python-cmd CMD             Python ${EXPECTED_PYTHON_VERSION} command. Optional.
  -h, --help                   Show this help

Examples:
  $0
  $0 --python-cmd python${EXPECTED_PYTHON_VERSION}
  $0 --python-cmd "py -${EXPECTED_PYTHON_VERSION}"
EOF
}

is_windows_bash() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

find_cmd() {
  local name="$1"
  shift

  for cmd in "$@"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done

  fail "Required command not found: $name"
}

run_python() {
  if [ -n "$PYTHON_CMD" ]; then
    # shellcheck disable=SC2086
    $PYTHON_CMD "$@"
  else
    fail "PYTHON_CMD is not set."
  fi
}

detect_python() {
  if [ -n "$PYTHON_CMD" ]; then
    return
  fi

  if command -v "python${EXPECTED_PYTHON_VERSION}" >/dev/null 2>&1; then
    PYTHON_CMD="python${EXPECTED_PYTHON_VERSION}"
    return
  fi

  if command -v python3 >/dev/null 2>&1 && python3 -c "import sys; exit(0 if sys.version_info[:2] == (${EXPECTED_PYTHON_MAJOR}, ${EXPECTED_PYTHON_MINOR}) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="python3"
    return
  fi

  if command -v python >/dev/null 2>&1 && python -c "import sys; exit(0 if sys.version_info[:2] == (${EXPECTED_PYTHON_MAJOR}, ${EXPECTED_PYTHON_MINOR}) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="python"
    return
  fi

  if command -v py >/dev/null 2>&1 && py "-${EXPECTED_PYTHON_VERSION}" -c "import sys; exit(0 if sys.version_info[:2] == (${EXPECTED_PYTHON_MAJOR}, ${EXPECTED_PYTHON_MINOR}) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="py -${EXPECTED_PYTHON_VERSION}"
    return
  fi

  fail "Python ${EXPECTED_PYTHON_VERSION} not found. Install Python ${EXPECTED_PYTHON_VERSION} or run with --python-cmd."
}

venv_python_cmd() {
  if is_windows_bash && [ -f ".venv/Scripts/python.exe" ]; then
    echo ".venv/Scripts/python.exe"
  elif is_windows_bash && [ -f ".venv/Scripts/python" ]; then
    echo ".venv/Scripts/python"
  elif [ -f ".venv/bin/python" ]; then
    echo ".venv/bin/python"
  else
    fail "Virtual environment Python not found."
  fi
}

venv_is_broken() {
  if [ ! -d .venv ]; then
    return 1
  fi

  if is_windows_bash; then
    [ ! -f ".venv/Scripts/python.exe" ] && [ ! -f ".venv/Scripts/python" ]
  else
    [ ! -f ".venv/bin/python" ]
  fi
}

validate_non_empty() {
  local name="$1"
  local value="$2"

  [ -n "$value" ] || fail "$name cannot be empty."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --python-cmd)
      [ "$#" -ge 2 ] || fail "--python-cmd requires a value."
      PYTHON_CMD="$2"
      validate_non_empty "--python-cmd" "$PYTHON_CMD"
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

echo "Checking prerequisites..."

require_cmd git
require_cmd docker

NODE_CMD="$(find_cmd node node node.exe)"
NPM_CMD="$(find_cmd npm npm npm.cmd)"

docker info >/dev/null 2>&1 || fail "Docker daemon is not running or is not accessible."

detect_python

PY_VERSION="$(run_python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
[ "$PY_VERSION" = "$EXPECTED_PYTHON_VERSION" ] || fail "$PYTHON_CMD must point to Python ${EXPECTED_PYTHON_VERSION}. Detected: ${PY_VERSION}"

NODE_VERSION="$("$NODE_CMD" -v 2>/dev/null || true)"
[ -n "$NODE_VERSION" ] || fail "Node is not installed or not available in PATH."

NODE_MAJOR="$(echo "$NODE_VERSION" | sed -E 's/^v([0-9]+).*/\1/')"
if [ "$NODE_MAJOR" != "$EXPECTED_NODE_MAJOR" ]; then
  echo "WARNING: Tested on Node ${EXPECTED_NODE_VERSION}. Detected: ${NODE_VERSION}."
fi

if [ -e "$DEV_DIR" ]; then
  fail "'$DEV_DIR' already exists. Remove it or rename it before running this script."
fi

APP_DIR="$(pwd)/${DEV_DIR}"

echo
echo "Configuration:"
echo "  APP_DIR:          $APP_DIR"
echo "  OS:               $(uname -s 2>/dev/null || echo unknown)"
echo "  PYTHON_CMD:       $PYTHON_CMD"
echo "  EXPECTED_PYTHON:  $EXPECTED_PYTHON_VERSION"
echo "  NODE_CMD:         $NODE_CMD"
echo "  NPM_CMD:          $NPM_CMD"
echo "  EXPECTED_NODE:    $EXPECTED_NODE_VERSION"
echo "  NODE_VERSION:     $NODE_VERSION"
echo

echo "Cloning repository into $DEV_DIR..."

git clone "$REPO_URL" "$DEV_DIR"
cd "$DEV_DIR"

[ -d frontend ] || fail "frontend directory not found after clone."
[ -d backend ] || fail "backend directory not found after clone."

echo
echo "Starting Redis..."

if docker inspect "$REDIS_CONTAINER" >/dev/null 2>&1; then
  echo "Redis container already exists. Starting it if needed..."
  docker start "$REDIS_CONTAINER" >/dev/null
else
  docker run -d --name "$REDIS_CONTAINER" -p "${REDIS_PORT}:6379" redis:latest redis-server --requirepass "$REDIS_PASSWORD" >/dev/null
fi

echo "Starting Postgres..."

if docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1; then
  echo "Postgres container already exists. Starting it if needed..."
  docker start "$POSTGRES_CONTAINER" >/dev/null
else
  docker run -d --name "$POSTGRES_CONTAINER" \
    -e POSTGRES_DB="$POSTGRES_DB" \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -p ${POSTGRES_PORT}:5432 \
    -v "$POSTGRES_VOLUME:/var/lib/postgresql/data" \
    postgres:16 >/dev/null
fi

echo "Waiting for Postgres..."

until docker exec "$POSTGRES_CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  sleep 1
done

echo
echo "Creating frontend .env..."

[ "$PROTOCOL" = "https" ] && WS_PROTOCOL="wss" || WS_PROTOCOL="ws"

cat > frontend/.env <<EOF
BACKEND_BASE_URL=${PROTOCOL}://${DEPLOYMENT_HOST}:${BACKEND_PORT}
VITE_BACKEND_BASE_WS=${WS_PROTOCOL}://${DEPLOYMENT_HOST}:${BACKEND_PORT}
EOF

echo
echo "Installing frontend dependencies..."

cd frontend
"$NPM_CMD" install
cd ..

echo
echo "Creating backend .env..."

cat > backend/.env <<EOF
IS_DEV_ENV=${IS_DEV_ENV}
PROTOCOL=${PROTOCOL}
DEPLOYMENT_HOST=${DEPLOYMENT_HOST}
NGINX_PORT=${NGINX_PORT}

BACKEND_SECRET_KEY=${BACKEND_SECRET_KEY}
SIGNING_SECRET=${SIGNING_SECRET}
BACKEND_BASE_URL=${PROTOCOL}://${DEPLOYMENT_HOST}:${BACKEND_PORT}

REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_ADDRESS=localhost
REDIS_PORT=${REDIS_PORT}

POSTGRES_ADDRESS=localhost
POSTGRES_PORT=${POSTGRES_PORT}
POSTGRES_NAME=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

echo
echo "Setting up backend virtual environment..."

cd backend

if venv_is_broken; then
  echo "Existing backend/.venv looks broken. Recreating it..."
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  run_python -m venv .venv
fi

VENV_PYTHON="$(venv_python_cmd)"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt

echo
echo "Running migrations..."

"$VENV_PYTHON" manage.py migrate
"$VENV_PYTHON" manage.py collectstatic --noinput

echo
echo "Creating admin user..."
"$VENV_PYTHON" manage.py createuser --staff --login "$ADMIN_LOGIN" --password "$ADMIN_PASSWORD"

cd ..

echo
echo "Creating helper scripts..."

if is_windows_bash; then
  BACKEND_ACTIVATE='source .venv/Scripts/activate'
else
  BACKEND_ACTIVATE='source .venv/bin/activate'
fi

cat > run-frontend.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "\$(dirname "\$0")/frontend"
"${NPM_CMD}" run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT}
EOF

cat > run-backend.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "\$(dirname "\$0")/backend"
${BACKEND_ACTIVATE}
python manage.py runserver 0.0.0.0:${BACKEND_PORT}
EOF

cat > run-celery.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "\$(dirname "\$0")/backend"
${BACKEND_ACTIVATE}

cleanup() {
  echo
  echo "Stopping Celery processes..."
  jobs -p | xargs -r kill 2>/dev/null || true
}

trap cleanup EXIT INT TERM

celery -A website worker -l INFO -P eventlet &
celery -A website worker -l INFO --pool=solo -Q wsQ &
celery -A website worker -l INFO --pool=solo -Q deletion -c 1 &
celery -A website beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &

wait
EOF

chmod +x run-frontend.sh run-backend.sh run-celery.sh


echo
echo "Developer setup complete."
echo
echo "Project directory:"
echo "  $APP_DIR"
echo "ADMIN login: "
echo "  $ADMIN_PASSWORD"
echo "ADMIN password: "
echo "  $ADMIN_LOGIN"
echo
echo "Start services in separate terminals:"
echo "  cd $APP_DIR"
echo "  ./run-backend.sh"
echo "  ./run-frontend.sh"
echo "  ./run-celery.sh"
echo
echo "Frontend:"
echo "  http://localhost:${FRONTEND_PORT}"
echo
echo "Backend:"
echo "  http://localhost:${BACKEND_PORT}"