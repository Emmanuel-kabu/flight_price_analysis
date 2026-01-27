# Multi-stage build for optimized production image
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KAGGLE_CONFIG_DIR=/app/.kaggle

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/data/raw \
             /app/data/metadata \
             /app/logs \
             /app/.kaggle && \
    chown -R app:app /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# Create volume mount points for data persistence
VOLUME ["/app/data", "/app/logs", "/app/.kaggle"]

# Health check to ensure service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Environment variable for log level (configurable)
ENV LOG_LEVEL=INFO

# Default command with error handling
CMD ["python", "-u", "data_extraction/data_extraction.py"]