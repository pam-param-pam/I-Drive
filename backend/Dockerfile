# ----------------------------
# 1️⃣ Builder stage
# ----------------------------
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies into /install
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# ----------------------------
# 2️⃣ Final stage (runtime)
# ----------------------------
FROM python:3.10-slim

WORKDIR /app/backend

# Install runtime dependencies (nano if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nano && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy app code from builder
COPY --from=builder /app /app/backend

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
