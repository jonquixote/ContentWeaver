#!/bin/bash
# start_all_services.sh
# Script to start all MoneyWeaver services

set -e

echo "Starting MoneyWeaver Services..."

# Navigate to the backend directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv312" ]; then
    echo "Activating Python 3.12 virtual environment..."
    source venv312/bin/activate
else
    echo "Error: Python 3.12 virtual environment not found!"
    exit 1
fi

# Clean up any existing processes
echo "Cleaning up existing processes..."
pkill -f "litellm" 2>/dev/null || true
pkill -f "celery" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
sleep 3

# Start LiteLLM proxy in background with simplified config (no database)
echo "Starting LiteLLM proxy..."
LITELLM_DISABLE_DATABASE=true LITELLM_DISABLE_AUTH=true NO_DOCS="True" NO_REDOC="True" DATABASE_URL="" litellm --config litellm_config.yaml --port 8000 > litellm_proxy.log 2>&1 &
LITELLM_PID=$!

# Wait a moment for LiteLLM proxy to start
sleep 5

# Check if LiteLLM proxy is running by checking the process
if ps -p $LITELLM_PID > /dev/null 2>&1; then
    echo "LiteLLM proxy is running (PID: $LITELLM_PID)"
else
    echo "Warning: LiteLLM proxy may not have started correctly. Check litellm_proxy.log for details."
fi

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A src.services.celery_app.celery_app worker --loglevel=info --queues=celery,video_generation > celery_worker.log 2>&1 &
CELERY_PID=$!

# Wait a moment for Celery to start
sleep 5

# Check if Celery worker is running
if ps -p $CELERY_PID > /dev/null; then
    echo "Celery worker is running (PID: $CELERY_PID)"
else
    echo "Warning: Celery worker may not have started correctly. Check celery_worker.log for details."
fi

# Start the Flask backend
echo "Starting Flask backend..."
python src/main.py > flask_backend.log 2>&1 &
FLASK_PID=$!

# Wait a moment for Flask to start
sleep 5

# Check if Flask backend is running
if ps -p $FLASK_PID > /dev/null; then
    echo "Flask backend is running (PID: $FLASK_PID)"
else
    echo "Warning: Flask backend may not have started correctly. Check flask_backend.log for details."
fi

echo ""
echo "Service Status:"
echo "==============="
echo "LiteLLM proxy: $(if ps -p $LITELLM_PID > /dev/null 2>&1; then echo 'RUNNING'; else echo 'NOT RUNNING'; fi)"
echo "Celery worker: $(if ps -p $CELERY_PID > /dev/null; then echo 'RUNNING'; else echo 'NOT RUNNING'; fi)"
echo "Flask backend: $(if ps -p $FLASK_PID > /dev/null; then echo 'RUNNING'; else echo 'NOT RUNNING'; fi)"

echo ""
echo "All services started successfully!"
echo "Backend API available at http://localhost:5004"
echo "LiteLLM proxy available at http://localhost:8000"
echo ""
echo "To stop services, run: ./stop_all_services.sh"
echo "To check logs, view: litellm_proxy.log, celery_worker.log, flask_backend.log"