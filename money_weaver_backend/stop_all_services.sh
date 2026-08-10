#!/bin/bash
# stop_all_services.sh
# Script to stop all MoneyWeaver services

echo "Stopping MoneyWeaver Services..."

# Navigate to the backend directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv312" ]; then
    echo "Activating Python 3.12 virtual environment..."
    source venv312/bin/activate
else
    echo "Warning: Python 3.12 virtual environment not found!"
fi

# Stop processes by killing them
echo "Stopping LiteLLM proxy..."
pkill -f "litellm" 2>/dev/null || echo "LiteLLM proxy not running"

echo "Stopping Celery worker..."
pkill -f "celery" 2>/dev/null || echo "Celery worker not running"

echo "Stopping Flask backend..."
pkill -f "python.*main.py" 2>/dev/null || echo "Flask backend not running"

# Wait a moment for processes to terminate
sleep 3

echo "All services stopped."