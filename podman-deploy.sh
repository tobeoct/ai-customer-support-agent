#!/bin/bash
# Podman deployment script for Memory-Enhanced Customer Support Agent

set -e

echo "🚀 Starting Customer Support Agent deployment with Podman..."

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo "❌ Podman is not installed. Please install Podman first."
    exit 1
fi

# Check if podman-compose is available
if ! command -v podman-compose &> /dev/null; then
    echo "⚠️  podman-compose not found. Using podman directly..."
    USE_COMPOSE=false
else
    USE_COMPOSE=true
fi

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "📋 Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
fi

if [ "$USE_COMPOSE" = true ]; then
    echo "🔧 Using podman-compose..."
    
    # Build and start services with podman-compose
    echo "🏗️  Building application image..."
    podman-compose build
    
    echo "🚀 Starting all services..."
    podman-compose up -d
    
    echo "🔍 Checking service health..."
    sleep 10
    podman-compose ps
    
else
    echo "🔧 Using podman directly..."
    
    # Create network
    echo "🌐 Creating network..."
    podman network create customer-support-network 2>/dev/null || true
    
    # Start databases first
    echo "🗄️  Starting PostgreSQL..."
    podman run -d \
        --name customer-support-postgres \
        --network customer-support-network \
        -e POSTGRES_DB=customer_support \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -p 5432:5432 \
        -v customer-support-postgres-data:/var/lib/postgresql/data \
        --health-cmd="pg_isready -U postgres" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=5 \
        postgres:15
    
    echo "📊 Starting Neo4j..."
    podman run -d \
        --name customer-support-neo4j \
        --network customer-support-network \
        -e NEO4J_AUTH=neo4j/password \
        -e NEO4J_PLUGINS='["apoc"]' \
        -e NEO4J_dbms_default__database=neo4j \
        -e NEO4J_dbms_memory_heap_initial__size=512m \
        -e NEO4J_dbms_memory_heap_max__size=1G \
        -p 7474:7474 \
        -p 7687:7687 \
        -v customer-support-neo4j-data:/data \
        --health-cmd="cypher-shell -u neo4j -p password 'RETURN 1'" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=5 \
        neo4j:5.13
    
    echo "⚡ Starting Redis..."
    podman run -d \
        --name customer-support-redis \
        --network customer-support-network \
        -p 6379:6379 \
        -v customer-support-redis-data:/data \
        --health-cmd="redis-cli ping" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=5 \
        redis:7-alpine redis-server --appendonly yes
    
    # Wait for databases to be healthy
    echo "⏳ Waiting for databases to be ready..."
    sleep 20
    
    # Build backend image
    echo "🏗️  Building backend image..."
    podman build -f backend/Dockerfile -t customer-support-backend:latest backend/
    
    # Build frontend image
    echo "🏗️  Building frontend image..."
    podman build -f frontend/Dockerfile -t customer-support-frontend:latest frontend/
    
    # Start backend application
    echo "🚀 Starting backend..."
    podman run -d \
        --name customer-support-backend \
        --network customer-support-network \
        -e DATABASE_URL=postgresql://postgres:postgres@customer-support-postgres:5432/customer_support \
        -e REDIS_URL=redis://customer-support-redis:6379/0 \
        -e NEO4J_URI=bolt://customer-support-neo4j:7687 \
        -e NEO4J_USER=neo4j \
        -e NEO4J_PASSWORD=password \
        -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
        -e DEBUG=true \
        -e PYTHONPATH=/app \
        -p 8000:8000 \
        -v ./logs:/app/logs \
        --health-cmd="curl -f http://localhost:8000/health" \
        --health-interval=30s \
        --health-timeout=10s \
        --health-retries=3 \
        --health-start-period=40s \
        customer-support-backend:latest
    
    # Start frontend
    echo "🌐 Starting frontend..."
    podman run -d \
        --name customer-support-frontend \
        --network customer-support-network \
        -p 80:80 \
        --health-cmd="wget --no-verbose --tries=1 --spider http://localhost/health" \
        --health-interval=30s \
        --health-timeout=5s \
        --health-retries=3 \
        --health-start-period=10s \
        customer-support-frontend:latest
fi

echo "✅ Deployment complete!"
echo ""
echo "🌐 Services available at:"
echo "  • Chat API: http://localhost:8000/chat"
echo "  • WebSocket: ws://localhost:8000/ws/{session_id}"
echo "  • API Docs: http://localhost:8000/docs (streamlined public API)"
echo "  • MCP Tools: Run 'python backend/app/mcp_server.py' for admin operations"
echo "  • Neo4j Browser: http://localhost:7474 (neo4j/password)"
echo ""
echo "🔍 To check logs:"
if [ "$USE_COMPOSE" = true ]; then
    echo "  podman-compose logs -f"
else
    echo "  podman logs -f memory-agent-app"
fi
echo ""
echo "🛑 To stop:"
if [ "$USE_COMPOSE" = true ]; then
    echo "  podman-compose down"
else
    echo "  ./podman-stop.sh"
fi