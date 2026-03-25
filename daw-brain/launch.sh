#!/bin/bash
# DAW Brain Launcher
# Starts the Flask server and opens the browser

cd "$(dirname "$0")"

# Kill any existing server on port 5050
lsof -ti:5050 | xargs kill 2>/dev/null
sleep 1

# Source zshrc for API key
source ~/.zshrc 2>/dev/null

echo "Starting DAW Brain..."
echo "Server: http://localhost:5050"
echo "Press Ctrl+C to stop"
echo ""

# Open browser after a short delay
(sleep 2 && open http://127.0.0.1:5050) &

# Start server
python3 app.py
