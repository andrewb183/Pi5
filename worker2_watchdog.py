#!/usr/bin/env python3
"""
Worker2 Watchdog - Ensures workers stay active and reload when stuck

Monitors:
- Worker process alive
- Workers actually processing (not idle with full queue)
- Auto-restart when stuck

Run: python3 worker2_watchdog.py
"""

import json
import time
import subprocess
import sys
from pathlib import Path

WORKER_STATUS_FILE = Path('worker2_status.json')
IDEAS_LOG_FILE = Path('ideas_log.json')
CHECK_INTERVAL = 30  # Check every 30 seconds
IDLE_THRESHOLD = 120  # Restart if all workers idle for 2 minutes with queue full

def is_worker_running():
    """Check if worker2 process is running"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'worker2.py'],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except:
        return False

def get_worker_status():
    """Get current worker status"""
    if not WORKER_STATUS_FILE.exists():
        return None
    
    try:
        with open(WORKER_STATUS_FILE) as f:
            return json.load(f)
    except:
        return None

def get_ideas_count():
    """Count ideas in ideas_log.json"""
    if not IDEAS_LOG_FILE.exists():
        return 0
    
    try:
        with open(IDEAS_LOG_FILE) as f:
            ideas = json.load(f)
            return len(ideas) if isinstance(ideas, list) else 0
    except:
        return 0

def restart_worker():
    """Restart worker2"""
    print("🔄 Restarting worker2...")
    
    # Kill existing
    subprocess.run(['pkill', '-f', 'worker2.py'], capture_output=True)
    time.sleep(2)
    
    # Start new
    subprocess.Popen(
        ['python3', '-u', 'worker2.py'],
        stdout=open('worker2.log', 'w'),
        stderr=subprocess.STDOUT,
        cwd=Path(__file__).parent
    )
    
    print("✅ Worker2 restarted")
    time.sleep(5)  # Let it initialize

def main():
    print("👁️  Worker2 Watchdog Started")
    print("=" * 60)
    print(f"Check interval: {CHECK_INTERVAL}s")
    print(f"Idle threshold: {IDLE_THRESHOLD}s")
    print("=" * 60)
    
    last_active_time = time.time()
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            
            # Check if process is running
            if not is_worker_running():
                print("❌ Worker2 not running!")
                restart_worker()
                last_active_time = time.time()
                continue
            
            # Check status
            status = get_worker_status()
            if not status:
                print("⚠️  No status file")
                continue
            
            # Count active workers
            active_count = sum(
                1 for w in status.get('workers', {}).values()
                if w.get('status') == 'working'
            )
            
            # Count ideas waiting
            ideas_count = get_ideas_count()
            queue_size = status.get('queue_size', 0) + status.get('slow_queue_size', 0)
            
            # Check if stuck (all idle with full backlog)
            if active_count == 0 and ideas_count > 10:
                elapsed = time.time() - last_active_time
                print(f"⚠️  All workers idle with {ideas_count} ideas queued ({elapsed:.0f}s idle)")
                
                if elapsed > IDLE_THRESHOLD:
                    print(f"🚨 Workers stuck idle for {elapsed:.0f}s - restarting!")
                    restart_worker()
                    last_active_time = time.time()
            else:
                # Workers active or queue empty - reset timer
                last_active_time = time.time()
                if active_count > 0:
                    print(f"✓ {active_count} workers active, {ideas_count} ideas, queue={queue_size}")
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Watchdog stopped")
        sys.exit(0)

if __name__ == "__main__":
    main()
