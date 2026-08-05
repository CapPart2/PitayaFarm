#!/bin/bash

# PITAYA Backend - Production Startup Script
# This script starts the Flask API with Gunicorn for production deployment

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values if not set in .env
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-5000}
WORKERS=${WORKERS:-4}
WORKER_CLASS=${WORKER_CLASS:-sync}
TIMEOUT=${TIMEOUT:-120}
LOG_LEVEL=${LOG_LEVEL:-info}

echo "Starting PITAYA Backend with Gunicorn..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Worker Class: $WORKER_CLASS"
echo "Timeout: $TIMEOUT"
echo "Log Level: $LOG_LEVEL"

# Start Gunicorn
gunicorn app:app \
    --bind $HOST:$PORT \
    --workers $WORKERS \
    --worker-class $WORKER_CLASS \
    --timeout $TIMEOUT \
    --log-level $LOG_LEVEL \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance
