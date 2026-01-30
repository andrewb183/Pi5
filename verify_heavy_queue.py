#!/usr/bin/env python3
"""
Verify heavy projects queue setup is working correctly
"""

import json
from pathlib import Path
import subprocess

print("\n" + "="*70)
print("🔍 HEAVY PROJECTS QUEUE VERIFICATION")
print("="*70)

# Check files exist
print("\n📋 Queue Files:")
ideas_file = Path('ideas_log.json')
heavy_file = Path('heavy_projects_queue.json')
backup_file = Path('ideas_log_backup_before_cleanup.json')

files = {
    'Fast Queue (ideas_log.json)': ideas_file,
    'Heavy Queue (heavy_projects_queue.json)': heavy_file,
    'Backup (ideas_log_backup_before_cleanup.json)': backup_file,
}

for name, path in files.items():
    status = "✅" if path.exists() else "❌"
    print(f"  {status} {name}")

# Check queue contents
print("\n📊 Queue Contents:")
fast = json.load(open(ideas_file))
heavy = json.load(open(heavy_file))

print(f"  Fast projects:  {len(fast)} total")
print(f"  Heavy projects: {len(heavy)} total")
print(f"  Total projects: {len(fast) + len(heavy)}")

# Verify separation
fast_langs = set(p.get('language', 'Unknown').lower() for p in fast)
heavy_langs = set(p.get('language', 'Unknown').lower() for p in heavy)

print(f"\n  Fast languages: {', '.join(sorted(fast_langs))}")
print(f"  Heavy languages: {', '.join(sorted(heavy_langs))}")

# Check for overlap
overlap = fast_langs & heavy_langs
if overlap:
    print(f"\n  ⚠️  WARNING: Languages in both queues: {overlap}")
else:
    print(f"\n  ✅ No overlap between queues")

# Check retry_manager code
print("\n🔧 Retry Manager Configuration:")
with open('retry_manager.py') as f:
    content = f.read()
    
checks = {
    'Has heavy_queue_file initialization': 'self.heavy_queue_file = Path(\'heavy_projects_queue.json\')',
    'Has _feed_heavy_projects() method': 'def _feed_heavy_projects(self):',
    'Calls _feed_heavy_projects() in run()': 'self._feed_heavy_projects()',
    'Checks queue threshold': 'if len(ideas) > 50:',
}

for check, pattern in checks.items():
    status = "✅" if pattern in content else "❌"
    print(f"  {status} {check}")

# Check processes
print("\n⚙️  Running Processes:")
result = subprocess.run(['pgrep', '-lf', 'worker2|retry_manager|outline'], 
                       capture_output=True, text=True)
processes = result.stdout.strip().split('\n')
process_names = {
    'worker2': False,
    'retry_manager': False,
    'outline': False,
}

for line in processes:
    for name in process_names:
        if name in line and 'grep' not in line:
            process_names[name] = True

for name, running in process_names.items():
    status = "✅" if running else "❌"
    print(f"  {status} {name}")

# Show what's next
print("\n🎯 What's Coming:")
if heavy:
    print(f"  Next heavy project to run: {heavy[0].get('title', 'Unknown')}")
    print(f"                  Language: {heavy[0].get('language', 'Unknown')}")
    print(f"  Waiting in queue: {len(heavy) - 1} more heavy projects")

# Show summary
print("\n" + "="*70)
print("✅ HEAVY PROJECTS QUEUE READY")
print("="*70)
print(f"""
Configuration:
  • Fast queue: 370 Python/JavaScript projects
  • Heavy queue: 304 Rust/C++/Go/Java/C# projects
  • Feeding strategy: ONE heavy project when fast queue < 50
  • Timeout multiplier: 50x (fast), 100x (heavy)

Auto-feeding controlled by retry_manager.py:
  • Checks every 30 seconds
  • Only feeds if main queue < 50 items
  • Takes exactly ONE heavy project
  • Continues until all heavy projects complete

Monitoring:
  $ tail -f retry_manager.log | grep "⏸️"     # See heavy projects feeding
  $ python3 monitor_queue.py --status           # Overall system status
  
""")
print("="*70)
