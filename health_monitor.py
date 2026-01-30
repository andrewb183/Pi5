#!/usr/bin/env python3
"""
Health Monitor - Detects and recovers from system stalls
- Monitors worker2, retry_manager, and outline processes
- Detects stale status files
- Detects ideas stuck in queue
- Detects queue file corruption
- Auto-restarts stuck processes
- Sends alerts
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import sys


class HealthMonitor:
    def __init__(self):
        self.status_file = Path('worker2_status.json')
        self.ideas_file = Path('ideas_log.json')
        self.retry_file = Path('implementation_outputs/retry_queue.json')
        self.qa_file = Path('QAissue.json')
        
        self.stale_threshold = 120  # 2 minutes
        self.check_interval = 30    # Check every 30 seconds
        self.stuck_ideas_threshold = 300  # 5 minutes
        
    def is_process_running(self, name):
        """Check if process is running."""
        result = subprocess.run(['pgrep', '-f', name], capture_output=True, text=True)
        pids = [p for p in result.stdout.strip().split('\n') if p]
        return pids
    
    def get_status_file_age(self):
        """Get age of status file in seconds."""
        if not self.status_file.exists():
            return None
        
        try:
            with open(self.status_file) as f:
                data = json.load(f)
            ts = data.get('timestamp', 0)
            if ts:
                age = (datetime.now() - datetime.fromtimestamp(ts)).total_seconds()
                return age
        except:
            pass
        return None
    
    def is_status_stale(self):
        """Check if status file is stale (not being updated)."""
        age = self.get_status_file_age()
        if age is None:
            return True
        return age > self.stale_threshold
    
    def check_ideas_stuck(self):
        """Check if ideas are stuck (in queue but not being processed for > threshold)."""
        if not self.ideas_file.exists():
            return False, None
        
        try:
            with open(self.ideas_file) as f:
                ideas = json.load(f)
            
            if not ideas:
                return False, None
            
            # Get status
            status = {}
            if self.status_file.exists():
                with open(self.status_file) as f:
                    status = json.load(f)
            
            active = sum(1 for w in status.get('workers', {}).values() 
                        if w.get('status') == 'working')
            
            # If ideas exist but no workers active AND status is stale = stuck
            if ideas and active == 0 and self.is_status_stale():
                return True, f"{len(ideas)} ideas waiting, no active workers"
        except:
            pass
        
        return False, None
    
    def check_file_corruption(self):
        """Check if queue files are corrupted."""
        issues = []
        
        for path in [self.ideas_file, self.retry_file, self.qa_file]:
            if not path.exists():
                continue
            
            try:
                with open(path) as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    issues.append(f"{path.name} is not a list")
            except json.JSONDecodeError:
                issues.append(f"{path.name} is corrupted JSON")
            except Exception as e:
                issues.append(f"{path.name} read error: {e}")
        
        return issues
    
    def diagnose(self):
        """Full system diagnostic."""
        print("\n" + "="*70)
        print("🏥 HEALTH MONITOR DIAGNOSTIC")
        print("="*70)
        print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
        print()
        
        issues = []
        warnings = []
        
        # 1. Process health
        print("1️⃣  PROCESS STATUS")
        print("-"*70)
        for proc in ['worker2.py', 'retry_manager.py', 'outline']:
            pids = self.is_process_running(proc)
            if pids:
                print(f"✅ {proc:20s} PID: {pids[0].split()[0]}")
            else:
                print(f"❌ {proc:20s} NOT RUNNING")
                issues.append(f"{proc} not running")
        print()
        
        # 2. Status file freshness
        print("2️⃣  STATUS FILE FRESHNESS")
        print("-"*70)
        age = self.get_status_file_age()
        if age is None:
            print("❌ Status file not found or unreadable")
            issues.append("Status file missing/unreadable")
        elif age > self.stale_threshold:
            print(f"❌ Status file STALE: {age:.0f}s old (threshold: {self.stale_threshold}s)")
            issues.append(f"Status file stale ({age:.0f}s)")
        else:
            print(f"✅ Status file fresh: {age:.0f}s old")
        print()
        
        # 3. Ideas queue
        print("3️⃣  IDEAS QUEUE STATUS")
        print("-"*70)
        if self.ideas_file.exists():
            try:
                with open(self.ideas_file) as f:
                    ideas = json.load(f)
                print(f"✅ ideas_log.json: {len(ideas)} items")
                
                if ideas:
                    stuck, msg = self.check_ideas_stuck()
                    if stuck:
                        print(f"⚠️  STUCK: {msg}")
                        warnings.append(msg)
            except:
                print("❌ ideas_log.json is corrupted")
                issues.append("ideas_log.json corrupted")
        else:
            print("⚠️  ideas_log.json not found")
        print()
        
        # 4. Queue file integrity
        print("4️⃣  QUEUE FILE INTEGRITY")
        print("-"*70)
        corruption_issues = self.check_file_corruption()
        if corruption_issues:
            for issue in corruption_issues:
                print(f"❌ {issue}")
                issues.append(issue)
        else:
            print("✅ All queue files valid")
        print()
        
        # 5. Retry queue
        print("5️⃣  RETRY QUEUE")
        print("-"*70)
        if self.retry_file.exists():
            try:
                with open(self.retry_file) as f:
                    retry = json.load(f)
                print(f"✅ retry_queue.json: {len(retry)} projects")
            except:
                print("❌ retry_queue.json is corrupted")
                issues.append("retry_queue.json corrupted")
        print()
        
        # Summary
        print("="*70)
        print("📊 SUMMARY")
        print("="*70)
        if not issues and not warnings:
            print("✅ SYSTEM HEALTHY - All checks passed")
            return True, []
        
        if warnings:
            print(f"⚠️  {len(warnings)} warning(s):")
            for w in warnings:
                print(f"   - {w}")
        
        if issues:
            print(f"❌ {len(issues)} critical issue(s):")
            for issue in issues:
                print(f"   - {issue}")
            return False, issues
        
        return True, warnings
    
    def auto_recover(self):
        """Attempt to auto-recover from detected issues."""
        print("\n" + "="*70)
        print("🔧 AUTO-RECOVERY")
        print("="*70)
        
        healthy, issues = self.diagnose()
        
        if healthy and not issues:
            print("✅ System is healthy, no recovery needed")
            return True
        
        recovered = []
        
        # 1. Restart stuck worker2
        if any('Status file stale' in str(i) or 'STUCK' in str(i) for i in issues):
            print("\n🔄 Restarting worker2 (status stale/ideas stuck)...")
            subprocess.run(['pkill', '-9', 'worker2.py'], capture_output=True)
            time.sleep(2)
            subprocess.Popen(['nohup', 'python3', '-u', 'worker2.py'], 
                           stdout=open('worker2.log', 'a'),
                           stderr=subprocess.STDOUT,
                           cwd='/home/pi/Desktop/test/create')
            time.sleep(3)
            recovered.append("worker2 restarted")
        
        # 2. Restart retry_manager if not running
        if any('retry_manager' in str(i) for i in issues):
            print("\n🔄 Restarting retry_manager...")
            subprocess.run(['pkill', '-9', 'retry_manager.py'], capture_output=True)
            time.sleep(1)
            subprocess.Popen(['nohup', 'python3', '-u', 'retry_manager.py'],
                           stdout=open('retry_manager.log', 'a'),
                           stderr=subprocess.STDOUT,
                           cwd='/home/pi/Desktop/test/create')
            time.sleep(2)
            recovered.append("retry_manager restarted")
        
        # 3. Fix corrupted files
        if any('corrupted' in str(i).lower() for i in issues):
            print("\n🔧 Fixing corrupted files...")
            if 'ideas_log.json corrupted' in str(issues):
                Path('ideas_log.json').write_text('[]')
                print("   ✓ Reset ideas_log.json")
                recovered.append("ideas_log.json reset")
            if 'retry_queue.json corrupted' in str(issues):
                Path('implementation_outputs/retry_queue.json').write_text('[]')
                print("   ✓ Reset retry_queue.json")
                recovered.append("retry_queue.json reset")
        
        print()
        print("="*70)
        print(f"✅ RECOVERED FROM {len(recovered)} issue(s)")
        for r in recovered:
            print(f"   - {r}")
        print("="*70)
        
        return len(recovered) > 0
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring loop."""
        print("\n🏥 Starting continuous health monitoring")
        print(f"   Check interval: {self.check_interval}s")
        print(f"   Stale threshold: {self.stale_threshold}s")
        print()
        
        cycle = 0
        while True:
            cycle += 1
            try:
                healthy, issues = self.diagnose()
                
                if not healthy:
                    print("\n⚠️  UNHEALTHY STATE DETECTED - Attempting recovery...")
                    self.auto_recover()
                
                print(f"\n⏰ Next check in {self.check_interval}s...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                print("\n\n⏹️  Health monitor stopped")
                sys.exit(0)
            except Exception as e:
                print(f"\n❌ Monitor error: {e}")
                time.sleep(self.check_interval)


def main():
    monitor = HealthMonitor()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--diagnose':
            monitor.diagnose()
        elif sys.argv[1] == '--recover':
            monitor.auto_recover()
        elif sys.argv[1] == '--monitor':
            monitor.run_continuous_monitoring()
    else:
        print("Usage:")
        print("  python3 health_monitor.py --diagnose     # One-time diagnostic")
        print("  python3 health_monitor.py --recover       # Attempt auto-recovery")
        print("  python3 health_monitor.py --monitor       # Continuous monitoring")
        sys.exit(1)


if __name__ == "__main__":
    main()
