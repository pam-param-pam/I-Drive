# ----------------------------
# Builder stage
# ----------------------------
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python packages into /install
RUN pip install --target=/install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# ----------------------------
# Final stage (runtime)
# ----------------------------
FROM python:3.10-slim

WORKDIR /app/backend

# Install runtime dependencies (nano included)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nano && \
    rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local/lib/python3.10/site-packages

# Copy app code from builder
COPY --from=builder /app /app/backend

# Optional: prune unnecessary files to shrink image
RUN find /usr/local/lib/python3.10/site-packages -name "__pycache__" -type d -exec rm -rf {} + \
    && find /usr/local/lib/python3.10/site-packages -name "*.pyc" -delete \
    && rm -rf /usr/local/lib/python3.10/site-packages/tests /usr/local/lib/python3.10/site-packages/docs

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
