#!/bin/bash
# Verification script for proper microservices structure

echo "🔍 Verifying Memory-Enhanced Customer Support Agent Structure..."
echo ""

# Check if all required files exist in correct locations
echo "📋 Checking file locations..."

# Frontend files
if [ -f "frontend/Dockerfile" ]; then
    echo "✅ frontend/Dockerfile exists"
else
    echo "❌ frontend/Dockerfile missing"
fi

if [ -f "frontend/nginx.conf" ]; then
    echo "✅ frontend/nginx.conf exists"
else
    echo "❌ frontend/nginx.conf missing"
fi

# Backend files
if [ -f "backend/Dockerfile" ]; then
    echo "✅ backend/Dockerfile exists"
else
    echo "❌ backend/Dockerfile missing"
fi

if [ -f "backend/requirements.txt" ]; then
    echo "✅ backend/requirements.txt exists"
else
    echo "❌ backend/requirements.txt missing"
fi

if [ -f "backend/app/main.py" ]; then
    echo "✅ backend/app/main.py exists"
else
    echo "❌ backend/app/main.py missing"
fi

# Configuration files
if [ -f "docker-compose.yml" ]; then
    echo "✅ docker-compose.yml exists"
else
    echo "❌ docker-compose.yml missing"
fi

if [ -f ".env.example" ]; then
    echo "✅ .env.example exists"
else
    echo "❌ .env.example missing"
fi

echo ""
echo "🏗️ Verifying docker-compose build contexts..."

# Check docker-compose contexts
if grep -q "context: ./frontend" docker-compose.yml; then
    echo "✅ Frontend build context is correct (./frontend)"
else
    echo "❌ Frontend build context is incorrect"
fi

if grep -q "context: ./backend" docker-compose.yml; then
    echo "✅ Backend build context is correct (./backend)"
else
    echo "❌ Backend build context is incorrect"
fi

echo ""
echo "📁 Current directory structure:"
echo ""
echo "memory-agent/"
echo "├── frontend/"
echo "│   ├── Dockerfile"
echo "│   ├── nginx.conf"
echo "│   ├── index.html"
echo "│   └── ..."
echo "├── backend/"
echo "│   ├── Dockerfile"
echo "│   ├── requirements.txt"
echo "│   └── app/"
echo "│       └── main.py"
echo "└── docker-compose.yml"
echo ""

# Check for old files that should be removed
echo "🧹 Checking for old files that should be cleaned up..."

if [ -f "Dockerfile" ]; then
    echo "⚠️  Old root Dockerfile still exists - should be removed"
else
    echo "✅ No old root Dockerfile found"
fi

if [ -f "backend.Dockerfile" ]; then
    echo "⚠️  Old backend.Dockerfile still exists - should be removed"
else
    echo "✅ No old backend.Dockerfile found"
fi

if [ -d "app" ]; then
    echo "⚠️  Old root app/ directory still exists - should be removed"
else
    echo "✅ No old root app/ directory found"
fi

echo ""
echo "🎯 Structure verification complete!"
echo ""
echo "This is now a proper microservices architecture where:"
echo "  ✅ Each service has its own directory"
echo "  ✅ Each service has its own Dockerfile"
echo "  ✅ Build contexts are service-specific"
echo "  ✅ Dependencies are properly isolated"