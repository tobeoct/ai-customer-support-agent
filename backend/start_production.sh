#!/bin/bash
# Production deployment script for Customer Support System

echo "🚀 Starting Customer Support System (Production Mode)"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "../venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python -m venv ../venv && source ../venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source ../venv/bin/activate

# Check dependencies
echo "📦 Checking dependencies..."
python -c "import fastapi, uvicorn, redis, sqlalchemy, neo4j" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies! Installing..."
    pip install -r requirements.txt
fi

# Create necessary directories
mkdir -p logs
mkdir -p ../data/documents

# Start the system
echo "🎯 Starting system components..."
echo "   📡 API Server will run on: http://localhost:8000"
echo "   ⚙️ ETL Worker will run in background"
echo "   📊 Health check: http://localhost:8000/health"
echo "   🛠️ MCP Tools available for agents"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=================================================="

# Run the system manager
python run_system.py