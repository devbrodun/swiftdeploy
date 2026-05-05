# Alpine keeps the final image well under 300 MB
FROM python:3.12-alpine

# Create a non-root user and group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create log directory and give ownership to appuser
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app/logs

# Switch to non-root user
USER appuser

# Environment defaults (overridden by docker-compose)
ENV MODE=stable \
    APP_VERSION=1.0.0 \
    APP_PORT=3000

EXPOSE 3000

# Log to stdout/stderr so Docker captures logs normally.
# This is simpler and more reliable than writing to a file inside the container.
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "2", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "main:app"]
