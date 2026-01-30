#!/usr/bin/env python3
"""
Verify Auto-Send is Enabled and Ideas are Processing
"""

import json
from pathlib import Path

print("=" * 70)
print("🔍 Verifying Auto-Send Configuration & Queued Ideas")
print("=" * 70)

# Check 1: outline auto_send setting
print("\n1. Checking outline.py auto_send setting...")
outline_path = Path('./outline')
if outline_path.exists():
    with open(outline_path, 'r') as f:
        content = f.read()
        if 'self.auto_send_enabled = True' in content:
            print("   ✅ auto_send_enabled = True (ENABLED)")
        else:
            print("   ❌ auto_send_enabled = False (DISABLED)")
else:
    print("   ❌ outline not found")

# Check 2: ideas_log.json
print("\n2. Checking ideas_log.json...")
ideas_log = Path('./ideas_log.json')
if ideas_log.exists():
    with open(ideas_log, 'r') as f:
        ideas = json.load(f)
    print(f"   ✅ Found {len(ideas)} ideas in queue")
    
    if len(ideas) > 0:
        print(f"\n   Sample ideas (first 5):")
        for i, idea in enumerate(ideas[:5], 1):
            print(f"      {i}. {idea.get('title', 'Unknown')} ({idea.get('language', 'Unknown')})")
else:
    print("   ❌ ideas_log.json not found")

# Check 3: mk14.py callable
print("\n3. Checking mk14.py...")
mk14_path = Path('./mk14.py')
if mk14_path.exists():
    print("   ✅ mk14.py found (ready to be called)")
else:
    print("   ❌ mk14.py not found")

# Check 4: worker2_status.json
print("\n4. Checking worker2 status...")
worker_status = Path('./worker2_status.json')
if worker_status.exists():
    with open(worker_status, 'r') as f:
        status = json.load(f)
    
    queue_size = status.get('queue_size', 0)
    completed = len([w for w in status.get('workers', {}).values() 
                     if w.get('last_completed') and w.get('last_completed') != 'None'])
    
    print(f"   Queue size: {queue_size}")
    print(f"   Tasks completed: {completed}")
else:
    print("   ⚠️  worker2_status.json not found (worker2 may not be running)")

# Check 5: error_log and retry_queue
print("\n5. Checking error logging & retry queue...")
error_log = Path('./implementations/error_log.json')
retry_queue = Path('./implementations/retry_queue.json')

if error_log.exists():
    with open(error_log, 'r') as f:
        errors = json.load(f)
    print(f"   📝 Error log: {len(errors)} errors logged")
else:
    print("   ℹ️  No error log yet (no failures)")

if retry_queue.exists():
    with open(retry_queue, 'r') as f:
        retries = json.load(f)
    print(f"   🔄 Retry queue: {len(retries)} items queued")
else:
    print("   ℹ️  No retry queue yet (no failures)")

# Summary
print("\n" + "=" * 70)
print("📊 SUMMARY")
print("=" * 70)

if ideas_log.exists():
    with open(ideas_log, 'r') as f:
        ideas = json.load(f)
    
    print(f"\n✅ READY TO PROCESS: {len(ideas)} ideas queued")
    print(f"\n🚀 What happens next:")
    print(f"   1. outline starts (auto_send_enabled = True)")
    print(f"   2. outline loads {len(ideas)} ideas from ideas_log.json")
    print(f"   3. outline AUTOMATICALLY sends each to mk14.py")
    print(f"   4. mk14 implements code with:")
    print(f"      • Code generation")
    print(f"      • Syntax/execution testing")
    print(f"      • QA verification (0-100 score)")
    print(f"      • Desktop move (if QA passed)")
    print(f"   5. worker2 queues/processes tasks")
    print(f"   6. monitor_queue.py shows progress")
    print(f"\n📋 To start processing:")
    print(f"   python3 outline  (if not already running)")
    print(f"\n📊 To monitor progress:")
    print(f"   python3 monitor_queue.py")
    print(f"\n✨ Check Desktop for completed projects!")
else:
    print("\n❌ No ideas_log.json found")

print()
