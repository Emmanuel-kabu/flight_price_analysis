#!/bin/bash

# Flight Price Analysis - Docker Setup Script

echo "Starting Flight Price Analysis Data Pipeline..."

# Check if required directories exist
echo "Checking directory structure..."
mkdir -p data/{raw,metadata}
mkdir -p logs
mkdir -p staging
mkdir -p analytics_and_prod
mkdir -p transformation
mkdir -p configuration
mkdir -p main

# Check if Kaggle credentials exist
if [ ! -f ~/.kaggle/kaggle.json ]; then
    echo "Kaggle credentials not found!"
    echo "Please:"
    echo "1. Go to https://www.kaggle.com/account"
    echo "2. Download your kaggle.json file"
    echo "3. Place it in ~/.kaggle/kaggle.json"
    echo "4. Run: chmod 600 ~/.kaggle/kaggle.json"
    exit 1
else
    echo "Kaggle credentials found"
fi

# Initialize Airflow database (first time only)
echo "Initializing Airflow database..."
docker-compose up airflow-postgres -d
sleep 10
docker-compose run --rm airflow-webserver airflow db init

# Create default Airflow admin user
echo "Creating Airflow admin user..."
docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin123

# Start all services
echo "Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Show service status
echo "Service Status:"
docker-compose ps

echo ""
echo "Flight Price Analysis Pipeline is ready!"
echo ""
echo "Access Points:"
echo "• Airflow UI: http://localhost:8080 (admin/admin123)"
echo "• Flower (monitoring): http://localhost:5555"
echo "• MySQL (staging): localhost:3306 (staging_user/staging_pass)"
echo "• PostgreSQL (analytics): localhost:5432 (analytics_user/analytics_pass)"
echo ""
echo "Data Flow:"
echo "1. Extract: Kaggle → flight-price-extractor → MySQL staging"
echo "2. Transform: DBT → PostgreSQL analytics"
echo "3. Orchestrate: Airflow manages the entire pipeline"
echo ""
echo "  Useful Commands:"
echo "• View logs: docker-compose logs -f [service-name]"
echo "• Stop all: docker-compose down"
echo "• Restart: docker-compose restart [service-name]"