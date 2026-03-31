#!/bin/bash

# SAR Platform - Demo Startup Script

echo ""
echo "=========================================="
echo "  SAR PLATFORM - STARTING DEMO SERVER"
echo "=========================================="
echo ""
echo "🚀 Starting web server..."
echo ""
echo "📍 Once started, open your browser to:"
echo "   http://localhost:8888"
echo ""
echo "⚠️  Press Ctrl+C to stop the server"
echo ""
echo "=========================================="
echo ""

cd "$(dirname "$0")"
python3 server.py
