FROM python:3.11-slim

# Set environment variables to ensure python output is not buffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Create a directory for persistent data
RUN mkdir -p /data

# Copy the application code
COPY essacache /app/essacache

# Install dependencies
RUN pip install prometheus-client prompt-toolkit rich

# Expose the standard port and prometheus port
EXPOSE 6379 8000

# Bind to 0.0.0.0 so it is accessible outside the container
# Store AOF and RDB inside the /data directory for persistence
CMD ["python3", "-m", "essacache", "--host", "0.0.0.0", "--port", "6379", "--aof", "/data/essacache.aof", "--rdb", "/data/essacache.rdb"]
