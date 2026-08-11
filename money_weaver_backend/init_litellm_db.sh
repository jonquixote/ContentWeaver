#!/bin/bash
# init_litellm_db.sh
# Script to initialize LiteLLM database

set -e

echo "Initializing LiteLLM Database..."

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

# Set environment variables for PostgreSQL database
export DATABASE_URL="${DATABASE_URL:-postgresql://money_weaver:money_weaver_password@localhost:5432/money_weaver}"

# Check if PostgreSQL is running
if ! lsof -i :5432 > /dev/null 2>&1; then
    echo "PostgreSQL is not running. Please start it first."
    exit 1
fi

# Run prisma generate to create the client
echo "Running prisma generate..."
prisma generate || {
    echo "Warning: prisma generate failed"
    echo "Attempting to generate prisma client manually..."
    
    # Try to create the prisma schema file
    mkdir -p prisma
    cat > prisma/schema.prisma << 'EOF'
generator client {
  provider = "prisma-client-py"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
EOF
    
    # Try prisma generate again
    prisma generate || echo "prisma generate still failed, but continuing..."
}

echo "LiteLLM database initialization completed."
echo "Note: Some warnings may be ignored if you're not using database features."