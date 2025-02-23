#!/bin/bash
echo "Replacing VITE_BACKEND_BASE_URL..."
# Ensure the environment variable is available
if [ -z "$VITE_BACKEND_BASE_URL" ]; then
  echo "Error: VITE_BACKEND_BASE_URL is not set"
  exit 1
fi
echo "Replacing with"
echo ${VITE_BACKEND_BASE_URL}
# Replace http with ws and https with wss for VITE_BACKEND_BASE_WS
# This is done to avoid a redundant env variable that just differs in protocol
VITE_BACKEND_BASE_WS="${VITE_BACKEND_BASE_URL/http:/ws://}"
VITE_BACKEND_BASE_WS="${VITE_BACKEND_BASE_WS/https:/wss://}"

# Loop through all files in the /var/www/idrive/frontend folder and replace the placeholder
find /var/www/idrive/frontend/assets -type f -exec sed -i "s|{{ VITE_BACKEND_BASE_URL }}|${VITE_BACKEND_BASE_URL}|g" {} \;
find /var/www/idrive/frontend/assets -type f -exec sed -i "s|{{ VITE_BACKEND_BASE_WS }}|${VITE_BACKEND_BASE_WS}|g" {} \;

echo "Starting nginx..."

# Now run the original NGINX entrypoint to start the server
exec nginx -g 'daemon off;'
