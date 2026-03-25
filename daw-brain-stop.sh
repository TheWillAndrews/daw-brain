#!/bin/bash
# DAW Brain — Stop Server

PIDFILE="$HOME/Desktop/TRK_TOOLS/daw-brain/.server.pid"

# Kill by PID file
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    kill "$PID" 2>/dev/null
    rm -f "$PIDFILE"
fi

# Also kill anything still on port 5050 (child processes)
PIDS=$(lsof -ti:5050 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null
fi

echo "DAW Brain server stopped."
