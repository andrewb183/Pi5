#!/bin/bash
# Auto-start worker2 if not running

WORKER2_DIR="/home/pi/Desktop/test/create"
cd "$WORKER2_DIR"

# Check if worker2 is already running
if pgrep -f "worker2.run_workers" > /dev/null; then
    echo "✓ worker2 already running"
    exit 0
fi

# Start worker2 in background
nohup python3 -c "import asyncio, worker2; asyncio.run(worker2.run_workers())" > worker2.log 2>&1 &
PID=$!

sleep 2

# Verify it started
if ps -p $PID > /dev/null; then
    echo "✓ worker2 started (PID: $PID)"
    echo "Monitor: tail -f $WORKER2_DIR/worker2.log"
else
    echo "✗ Failed to start worker2"
    exit 1
fi
