#!/bin/bash

echo "Starting VITE_BACKEND_BASE_URL replacement script..."

# Ensure the environment variable is available
if [ -z "$VITE_BACKEND_BASE_URL" ]; then
  echo "Error: VITE_BACKEND_BASE_URL is not set"
  exit 1
fi

echo "Using VITE_BACKEND_BASE_URL: $VITE_BACKEND_BASE_URL"

# Derive WS URL from HTTP/HTTPS
VITE_BACKEND_BASE_WS="${VITE_BACKEND_BASE_URL/http:/ws://}"
VITE_BACKEND_BASE_WS="${VITE_BACKEND_BASE_WS/https:/wss://}"

echo "Derived VITE_BACKEND_BASE_WS: $VITE_BACKEND_BASE_WS"

# Replace in uncompressed files
echo "Replacing placeholders in regular (uncompressed) files..."
find /var/www/idrive/frontend/assets -type f ! -name "*.gz" | while read file; do
  echo "Updating $file"
  sed -i "s|{{ VITE_BACKEND_BASE_URL }}|${VITE_BACKEND_BASE_URL}|g" "$file"
  sed -i "s|{{ VITE_BACKEND_BASE_WS }}|${VITE_BACKEND_BASE_WS}|g" "$file"
done

# Replace in .gz files
echo "Processing compressed (.gz) files..."
find /var/www/idrive/frontend/assets -type f -name "*.gz" | while read gzfile; do
  echo " Decompressing and updating $gzfile"

  tempfile="${gzfile%.gz}.tmp"

  # Uncompress to temp file
  gunzip -c "$gzfile" > "$tempfile"

  # Replace placeholders
  sed -i "s|{{ VITE_BACKEND_BASE_URL }}|${VITE_BACKEND_BASE_URL}|g" "$tempfile"
  sed -i "s|{{ VITE_BACKEND_BASE_WS }}|${VITE_BACKEND_BASE_WS}|g" "$tempfile"

  # Recompress back to original file
  gzip -c "$tempfile" > "$gzfile"

  # Clean up temp file
  rm "$tempfile"
done

echo "All replacements completed successfully."

echo "Starting nginx..."
# Now run the original NGINX entrypoint to start the server
exec nginx -g 'daemon off;'