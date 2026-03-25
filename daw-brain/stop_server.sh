#!/bin/bash
PORT=5050
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/.server.pid"

echo "Stopping DAW Brain server..."

STOPPED=0

# Try PID file first
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        sleep 1
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID"
        fi
        echo "Stopped PID $PID"
        STOPPED=1
    fi
    rm -f "$PID_FILE"
fi

# Kill anything still on the port
REMAINING=$(lsof -ti ":$PORT" 2>/dev/null)
if [ -n "$REMAINING" ]; then
    echo "$REMAINING" | xargs kill 2>/dev/null
    echo "Killed remaining processes on port $PORT"
    STOPPED=1
fi

if [ $STOPPED -eq 1 ]; then
    echo "DAW Brain stopped."
else
    echo "No running server found."
fi
