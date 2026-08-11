#!/bin/bash

# Start script for MoneyWeaver application
# This script starts all required services for the MoneyWeaver application

set -e  # Exit on any error

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "Starting MoneyWeaver application..."

# Function to check if a service is running
check_service() {
    if pgrep -f "$1" > /dev/null; then
        echo "$2 is already running"
        return 0
    else
        return 1
    fi
}

# Function to start Docker services
start_docker_services() {
    echo "Starting Docker services..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Start all services defined in docker-compose.yml
    docker-compose up -d
    
    echo "Waiting for services to start..."
    sleep 10
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        echo "Docker services started successfully"
    else
        echo "Warning: Some Docker services may not have started correctly"
        docker-compose ps
    fi
}

# Function to start services without Docker (development mode)
start_local_services() {
    echo "Starting local services..."
    
    # Start Redis server if not already running
    if ! check_service "redis-server" "Redis"; then
        echo "Starting Redis server..."
        if command -v redis-server > /dev/null; then
            redis-server --daemonize yes
            sleep 2
            echo "Redis server started"
        else
            echo "Warning: Redis server not found. Please install Redis to use local mode."
        fi
    fi
    
    # Start the Flask backend API
    if ! check_service "src/main.py" "Flask API"; then
        echo "Starting Flask API server..."
        source venv/bin/activate && python src/main.py > flask.log 2>&1 &
        echo $! > flask.pid
        sleep 3
        echo "Flask API server started"
    fi
    
    # Start Celery worker
    if ! check_service "celery worker" "Celery Worker"; then
        echo "Starting Celery worker..."
        source venv/bin/activate && celery -A src.services.celery_app worker --loglevel=info -Q celery,video_generation > celery.log 2>&1 &
        echo $! > celery.pid
        sleep 3
        echo "Celery worker started"
    fi
}

# Function to start the frontend
start_frontend() {
    echo "Starting frontend..."
    cd ../money_weaver_frontend
    
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        pnpm install
    fi
    
    echo "Starting frontend development server..."
    pnpm dev > frontend.log 2>&1 &
    echo $! > frontend.pid
    cd ../money_weaver_backend
    
    sleep 5
    echo "Frontend development server started"
}

# Function to stop all services
stop_services() {
    echo "Stopping all services..."
    
    # Stop Docker services if running
    if docker-compose ps > /dev/null 2>&1; then
        echo "Stopping Docker services..."
        docker-compose down
    fi
    
    # Kill local services if running
    if [ -f "flask.pid" ]; then
        echo "Stopping Flask API server..."
        kill $(cat flask.pid) 2>/dev/null || true
        rm flask.pid
    fi
    
    if [ -f "celery.pid" ]; then
        echo "Stopping Celery worker..."
        kill $(cat celery.pid) 2>/dev/null || true
        rm celery.pid
    fi
    
    if [ -f "../money_weaver_frontend/frontend.pid" ]; then
        echo "Stopping frontend server..."
        kill $(cat ../money_weaver_frontend/frontend.pid) 2>/dev/null || true
        rm ../money_weaver_frontend/frontend.pid
    fi
    
    echo "All services stopped"
}

# Main execution
case "$1" in
    "docker")
        start_docker_services
        ;;
    "local")
        start_local_services
        start_frontend
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        start_docker_services
        ;;
    *)
        echo "Usage: $0 {docker|local|stop|restart}"
        echo "  docker   - Start all services using Docker (recommended)"
        echo "  local    - Start services locally without Docker"
        echo "  stop     - Stop all running services"
        echo "  restart  - Restart all Docker services"
        exit 1
        ;;
esac

echo "Start script completed"