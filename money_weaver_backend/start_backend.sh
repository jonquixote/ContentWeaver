#!/bin/bash
# start_backend.sh
# Startup script for MoneyWeaver backend

set -e  # Exit on any error

echo "Starting MoneyWeaver Backend Setup..."

# Navigate to the backend directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Error: Virtual environment not found!"
    exit 1
fi

# Run database cleanup
echo "Running database cleanup..."
python cleanup_databases.py

# Verify database file exists and has correct permissions
DB_PATH="database/app.db"
if [ -f "$DB_PATH" ]; then
    echo "Setting correct permissions on database..."
    chmod 666 "$DB_PATH"
    chmod 777 "$(dirname "$DB_PATH")"
else
    echo "Warning: Database file not found at $DB_PATH"
fi

# Start the backend application
echo "Starting backend application..."
python src/main.py