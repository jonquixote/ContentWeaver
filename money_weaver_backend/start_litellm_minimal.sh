#!/bin/bash
# start_litellm_minimal.sh
# Minimal script to start LiteLLM proxy without database

set -e

echo "Starting LiteLLM proxy with minimal configuration..."

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

# Set environment variables to disable database completely
export LITELLM_DISABLE_DATABASE=true
export LITELLM_DISABLE_AUTH=true
export NO_DOCS="True"
export NO_REDOC="True"
export DATABASE_URL=""
export LITELLM_DATABASE_URL=""

# Create a minimal config file
cat > minimal_config.yaml << 'EOF'
model_list:
  - model_name: llama-3.1-8b-instant
    litellm_params:
      model: groq/llama-3.1-8b-instant
      api_key: REDACTED_GROQ_API_KEY

litellm_settings:
  drop_params: True

general_settings: 
  master_key: sk-master-key-change-me
  disable_auth: true
  store_model_in_db: false
EOF

# Start LiteLLM proxy with minimal config
echo "Starting LiteLLM proxy..."
litellm --config minimal_config.yaml --port 8000 > litellm_minimal.log 2>&1 &
LITELLM_PID=$!

# Wait a moment for LiteLLM proxy to start
sleep 5

# Check if LiteLLM proxy is running
if lsof -i :8000 > /dev/null 2>&1; then
    echo "LiteLLM proxy is running (PID: $LITELLM_PID)"
else
    echo "Warning: LiteLLM proxy may not have started correctly. Check litellm_minimal.log for details."
fi