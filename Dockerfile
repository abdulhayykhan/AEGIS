FROM python:3.12-slim

# Security: Install updates and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root service user for production isolation
RUN useradd -m -u 1000 -s /bin/bash aegis
WORKDIR /app

# Install dependencies first for optimal caching
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY --chown=aegis:aegis . .

# Install package in production mode
RUN pip install --no-cache-dir -e .

USER aegis

# Default entrypoint is the unified AEGIS CLI
ENTRYPOINT ["aegis"]
CMD ["dashboard"]
