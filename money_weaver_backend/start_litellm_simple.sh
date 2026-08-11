#!/bin/bash
# start_litellm_simple.sh
# Simple script to start LiteLLM proxy

set -e

echo "Starting LiteLLM proxy with simple configuration..."

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

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Set environment variables to disable database completely (overrides .env)
export LITELLM_DISABLE_DATABASE=true
export NO_DOCS="True"
export NO_REDOC="True"
export DATABASE_URL=""
export LITELLM_DATABASE_URL=""

# Try starting LiteLLM with just a model parameter instead of a config file
echo "Starting LiteLLM proxy with direct model parameter..."
if [ -z "${GROQ_API_KEY}" ]; then
    echo "Error: GROQ_API_KEY is not set. Add it to .env and retry."
    exit 1
fi
litellm --model groq/llama-3.1-8b-instant --add_key "${GROQ_API_KEY}" --port 8000 > litellm_simple.log 2>&1 &
LITELLM_PID=$!

# Wait a moment for LiteLLM proxy to start
sleep 5

# Check if LiteLLM proxy is running
if lsof -i :8000 > /dev/null 2>&1; then
    echo "LiteLLM proxy is running (PID: $LITELLM_PID)"
else
    echo "Warning: LiteLLM proxy may not have started correctly. Check litellm_simple.log for details."
fi