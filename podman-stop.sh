#!/bin/bash
# Podman stop script for Customer Support Agent

set -e

echo "🛑 Stopping Customer Support Agent..."

# Check if podman-compose is available
if command -v podman-compose &> /dev/null && [ -f docker-compose.yml ]; then
    echo "🔧 Using podman-compose..."
    podman-compose down
else
    echo "🔧 Using podman directly..."
    
    # Stop containers
    echo "🛑 Stopping containers..."
    podman stop customer-support-frontend customer-support-backend customer-support-postgres customer-support-neo4j customer-support-redis 2>/dev/null || true
    
    # Remove containers
    echo "🗑️  Removing containers..."
    podman rm customer-support-frontend customer-support-backend customer-support-postgres customer-support-neo4j customer-support-redis 2>/dev/null || true
    
    # Remove network
    echo "🌐 Removing network..."
    podman network rm customer-support-network 2>/dev/null || true
fi

echo "✅ All services stopped!"
echo ""
echo "💡 To remove all data volumes:"
echo "  podman volume rm customer-support-postgres-data customer-support-neo4j-data customer-support-redis-data 2>/dev/null || true"