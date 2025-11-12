#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                     POLISH IAMD C2 SYSTEM - STARTUP                                  ║"
echo "║                                                                                       ║"
echo "║  For: Polish Ministry of National Defence                                            ║"
echo "║  Deputy Director: Paweł Bejda                                                        ║"
echo "║  Focus: Kaliningrad Corridor + Coalition IAMD                                        ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🔧 Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Check pip packages
echo "📦 Checking Python packages..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "Installing fastapi..."
    pip3 install fastapi
}

python3 -c "import uvicorn" 2>/dev/null || {
    echo "Installing uvicorn..."
    pip3 install uvicorn
}

python3 -c "import requests" 2>/dev/null || {
    echo "Installing requests..."
    pip3 install requests
}

echo ""
echo "✅ All dependencies installed"
echo ""
echo "🚀 Starting Polish IAMD C2 Service..."
echo ""
echo "   🌍 Web Interface: http://localhost:8003"
echo "   📚 API Docs:      http://localhost:8003/docs"
echo "   🎯 Validation:    POST http://localhost:8003/api/validate-kaliningrad"
echo ""
echo "   ⚡ ARBITER:       https://api.arbiter.traut.ai/v1/compare (remote)"
echo ""
echo "Architecture:"
echo "   Browser → Polish C2 (localhost:8003) → ARBITER API (remote) → Results"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

# Start the service
python3 polish_c2_api.py
