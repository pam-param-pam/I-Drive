# ----------------------------
# 1️⃣ Builder stage
# ----------------------------
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies into /install and reuse pip's download cache.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

# ----------------------------
# 2️⃣ Final stage (runtime)
# ----------------------------
FROM python:3.12-slim

WORKDIR /app/backend

# Install runtime dependencies (nano if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nano && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy app code
COPY . .

# Collect Django static files into the image at build time.
RUN python manage.py collectstatic --noinput --settings=website.collectstatic_settings

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
