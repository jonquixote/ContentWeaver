#!/bin/bash
# start_all_services.sh
# Script to start all MoneyWeaver services

set -e

echo "Starting MoneyWeaver Services..."

# Navigate to the backend directory
cd "$(dirname "$0")"

# Virtual environment check (no `activate` — it hardcodes a stale VIRTUAL_ENV path)
if [ ! -x "venv/bin/python" ]; then
    echo "Error: virtual environment not found!"
    exit 1
fi

# Clean up any existing processes
echo "Cleaning up existing processes..."
pkill -f "celery" 2>/dev/null || true
pkill -f "python.*run.py" 2>/dev/null || true
sleep 3

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Start Celery worker in background
echo "Starting Celery worker..."
venv/bin/celery -A src.services.celery_app.celery_app worker --loglevel=info --queues=celery,video_generation > celery_worker.log 2>&1 &
CELERY_PID=$!

# Wait a moment for Celery to start
sleep 5

# Check if Celery worker is running
if ps -p $CELERY_PID > /dev/null; then
    echo "Celery worker is running (PID: $CELERY_PID)"
else
    echo "Warning: Celery worker may not have started correctly. Check celery_worker.log for details."
fi

# Start the FastAPI backend
echo "Starting FastAPI backend..."
venv/bin/python run.py > fastapi_backend.log 2>&1 &
FASTAPI_PID=$!

# Wait a moment for FastAPI to start
sleep 5

# Check if FastAPI backend is running
if ps -p $FASTAPI_PID > /dev/null; then
    echo "FastAPI backend is running (PID: $FASTAPI_PID)"
else
    echo "Warning: FastAPI backend may not have started correctly. Check fastapi_backend.log for details."
fi

echo ""
echo "Service Status:"
echo "==============="
echo "Celery worker: $(if ps -p $CELERY_PID > /dev/null; then echo 'RUNNING'; else echo 'NOT RUNNING'; fi)"
echo "FastAPI backend: $(if ps -p $FASTAPI_PID > /dev/null; then echo 'RUNNING'; else echo 'NOT RUNNING'; fi)"

echo ""
echo "All services started successfully!"
echo "Backend API available at http://localhost:5004"
echo ""
echo "To stop services, run: ./stop_all_services.sh"
echo "To check logs, view: celery_worker.log, fastapi_backend.log"
