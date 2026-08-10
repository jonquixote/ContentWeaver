#!/bin/bash
# test_litellm.sh
# Test script to check if LiteLLM works with minimal config

set -e

echo "Testing LiteLLM with minimal configuration..."

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

# Set environment variables to disable database
export LITELLM_DISABLE_DATABASE=true
export LITELLM_DISABLE_AUTH=true
export NO_DOCS="True"
export NO_REDOC="True"
export DATABASE_URL=""

# Start LiteLLM proxy with minimal config
echo "Starting LiteLLM proxy with minimal config..."
litellm --config minimal_litellm_config.yaml --port 8001 > litellm_test.log 2>&1 &
LITELLM_PID=$!

# Wait a moment for LiteLLM proxy to start
sleep 5

# Check if LiteLLM proxy is running
if lsof -i :8001 > /dev/null 2>&1; then
    echo "LiteLLM proxy is running (PID: $LITELLM_PID)"
    echo "Test successful!"
    
    # Stop the process
    kill $LITELLM_PID 2>/dev/null || true
    sleep 2
else
    echo "Test failed. Check litellm_test.log for details."
    cat litellm_test.log
fi