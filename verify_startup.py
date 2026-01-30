#!/usr/bin/env python3
"""
Startup Verification - Checks all systems before starting outline
Quick check to ensure error logging, retry queue, and timeouts are configured
"""

import sys
from pathlib import Path
import json

def verify_startup():
    """Quick verification that all systems are ready."""
    print("=" * 60)
    print("🔍 System Startup Verification")
    print("=" * 60)
    
    all_ok = True
    
    # Check 1: mk14.py exists
    print("\n1. Checking mk14.py...")
    mk14_path = Path('./mk14.py')
    if mk14_path.exists():
        print("   ✅ mk14.py found")
        
        # Check timeout multiplier
        with open(mk14_path, 'r') as f:
            content = f.read()
            if "MK14_TIMEOUT_MULTIPLIER', '20'" in content:
                print("   ✅ Timeout multiplier: 20x (old hardware mode)")
            elif "MK14_TIMEOUT_MULTIPLIER', '10'" in content:
                print("   ⚠️  Timeout multiplier: 10x (consider 20x for slower hardware)")
            
            # Check error logging methods
            if "_log_error" in content and "_add_to_retry_queue" in content:
                print("   ✅ Error logging methods present")
            else:
                print("   ❌ Error logging methods missing")
                all_ok = False
    else:
        print("   ❌ mk14.py not found")
        all_ok = False
    
    # Check 2: outline script exists
    print("\n2. Checking outline script...")
    outline_path = Path('./outline')
    if outline_path.exists():
        print("   ✅ outline script found")
        
        # Check if it calls mk14
        with open(outline_path, 'r') as f:
            content = f.read()
            if 'mk14.py' in content:
                print("   ✅ outline → mk14 integration configured")
            else:
                print("   ⚠️  outline doesn't call mk14")
    else:
        print("   ❌ outline script not found")
        all_ok = False
    
    # Check 3: Implementation directory
    print("\n3. Checking implementations directory...")
    impl_dir = Path('./implementations')
    if not impl_dir.exists():
        impl_dir.mkdir(exist_ok=True)
        print("   ✅ Created implementations directory")
    else:
        print("   ✅ implementations directory exists")
    
    # Check 4: Error logging files (create if needed)
    print("\n4. Checking error logging files...")
    error_log_path = impl_dir / 'error_log.json'
    retry_queue_path = impl_dir / 'retry_queue.json'
    
    if not error_log_path.exists():
        with open(error_log_path, 'w') as f:
            json.dump([], f)
        print("   ✅ Created error_log.json")
    else:
        with open(error_log_path, 'r') as f:
            error_log = json.load(f)
        print(f"   ✅ error_log.json exists ({len(error_log)} entries)")
    
    if not retry_queue_path.exists():
        with open(retry_queue_path, 'w') as f:
            json.dump([], f)
        print("   ✅ Created retry_queue.json")
    else:
        with open(retry_queue_path, 'r') as f:
            retry_queue = json.load(f)
        print(f"   ✅ retry_queue.json exists ({len(retry_queue)} items)")
    
    # Check 5: Import test
    print("\n5. Testing mk14 import...")
    try:
        from mk14 import CodeImplementer
        print("   ✅ mk14 imports successfully")
        
        # Test timeout configuration
        test_ci = CodeImplementer({'title': 'test', 'code': 'print(1)'})
        print(f"   ✅ Timeout multiplier: {test_ci.timeout_multiplier}x")
        print(f"   ✅ Error log path: {test_ci.error_log_path}")
        print(f"   ✅ Retry queue path: {test_ci.retry_queue_path}")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        all_ok = False
    
    # Check 6: Retry queue processor
    print("\n6. Checking retry queue processor...")
    retry_processor_path = Path('./process_retry_queue.py')
    if retry_processor_path.exists():
        print("   ✅ process_retry_queue.py found")
    else:
        print("   ⚠️  process_retry_queue.py not found")
    
    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL SYSTEMS READY!")
        print("=" * 60)
        print("\n🚀 You can now start outline:")
        print("   python3 outline")
        print("\n📋 How it works:")
        print("   1. outline generates/loads code ideas")
        print("   2. outline calls mk14.py automatically")
        print("   3. mk14 implements with error logging")
        print("   4. Errors logged to implementations/error_log.json")
        print("   5. Failed projects queued in implementations/retry_queue.json")
        print("   6. Run process_retry_queue.py to retry failures")
        print("\n⏱️  Hardware optimization:")
        print("   • 20x timeout multiplier for old hardware")
        print("   • Python: 5s → 100s")
        print("   • Rust: 30s → 600s (10 minutes)")
        print("   • API: 30s → 600s (10 minutes)")
        print("\n📊 Monitoring:")
        print("   • Errors: cat implementations/error_log.json | jq .")
        print("   • Retries: cat implementations/retry_queue.json | jq .")
        print("   • Process: python3 process_retry_queue.py")
        print()
        return 0
    else:
        print("❌ SOME SYSTEMS NOT READY")
        print("=" * 60)
        print("\n⚠️  Please check the issues above before starting outline")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(verify_startup())
