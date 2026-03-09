FROM python:3.11-slim

WORKDIR /app

# Install curl (needed for the health check below)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# This is done before copying app code so Docker can cache this layer
# (if only app code changes, pip install doesn't re-run)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app/ ./app/

# Copy the legacy Neo4j helper modules that app/graph.py re-exports
COPY Neo4j/ ./Neo4j/

# Copy fixture data (needed by the seed script)
COPY fixtures/ ./fixtures/

# Tell Docker this container listens on port 8000
EXPOSE 8000

# Health check — Docker uses this to know when ORC is ready
# docker-compose will wait for this to pass before starting dependent services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start the ORC FastAPI app
# --host 0.0.0.0 is required — without it the API is unreachable from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
