# Qdrant wrapper image with curl for proper HTTP health checks
# This enables production-aligned readiness probes against /readyz
#
# Why: Official qdrant/qdrant image deliberately excludes curl/wget
# for security reasons. We add only curl for health checks.
#
# Usage: Built automatically by docker-compose.yml

FROM qdrant/qdrant:v1.12.0

# Install curl for HTTP health checks (Alpine-based image)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Health check using proper HTTP readiness endpoint
# /readyz returns 200 when Qdrant is ready to serve requests
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:6333/readyz || exit 1

# No CMD override - use upstream entrypoint
