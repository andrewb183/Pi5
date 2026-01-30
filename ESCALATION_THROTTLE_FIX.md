# Escalation Throttling Fix - Summary

**Status**: ✅ IMPLEMENTED  
**Date**: 21 January 2026

---

## Problem

All 10 workers were processing variations of the same failed project (stable-diffusion-webui), blocking the entire queue:
- 20 escalation variations created per failed project
- All 10 workers grabbed these variations simultaneously
- Each took 10+ minutes to timeout
- Queue stalled for extended periods

---

## Solution Implemented

### 1. Reduced Escalation Variations (20 → 8)

**File**: `escalating_retry_system.py`

**Before**: 5 variations × 4 levels = 20 total
**After**: 2 variations × 4 levels = 8 total

```python
for level_idx, level in enumerate(levels):
    for variation in range(2):  # Changed from 5 to 2
```

**Impact**: 60% fewer variations per failed project

### 2. Added Concurrency Throttling

**File**: `worker2.py`

**New tracking**:
```python
ACTIVE_BASE_PROJECTS = {}  # {base_project_name: count}
MAX_CONCURRENT_SAME_PROJECT = 3  # Max 3 workers per base project
```

**Worker logic**:
- Before processing task, check if too many workers on same base project
- If ≥3 workers active on same project → requeue task and skip
- After task completes → decrement counter

**Example**:
```
Worker 0 starts: stable-diffusion-webui (count: 1)
Worker 1 starts: stable-diffusion-webui (count: 2)
Worker 2 starts: stable-diffusion-webui (count: 3)
Worker 3 tries:  "⏸️  Skipping - 3 workers already on 'stable-diffusion-webui'"
Worker 3 requeues task → processes different project
```

### 3. Added Priority Scoring

**File**: `escalating_retry_system.py`

```python
'priority': 5 + level_idx  # Conservative=5, Moderate=6, Aggressive=7, Nuclear=8
```

**Impact**: Fresh projects prioritized over aggressive retries

---

## How It Works

### Before (Problem)
```
Queue: [stable-diffusion L1-v1, L1-v2, L1-v3, ... L4-v5] (20 variations)
Worker 0-9: All grab stable-diffusion variations
Result: All 10 workers blocked for 10+ minutes each
```

### After (Solution)
```
Queue: [stable-diffusion L1-v1, L1-v2, L2-v1, ... L4-v2] (8 variations)
Worker 0: Grabs stable-diffusion L1-v1 (count: 1)
Worker 1: Grabs stable-diffusion L1-v2 (count: 2)
Worker 2: Grabs stable-diffusion L2-v1 (count: 3)
Worker 3: Tries stable-diffusion L2-v2 → THROTTLED (count ≥ 3)
Worker 3: Requeues → grabs fresh project instead
Result: Max 3 workers on failed project, 7 workers on fresh work
```

---

## Configuration

### Adjust throttle limit

**Edit**: `worker2.py` line ~78
```python
MAX_CONCURRENT_SAME_PROJECT = 3  # Change to 2, 4, etc.
```

**2 workers**: Very strict, minimal retry overhead
**3 workers**: Balanced (recommended)
**4-5 workers**: More aggressive retry attempts

### Adjust variation count

**Edit**: `escalating_retry_system.py` line ~393
```python
for variation in range(2):  # Change to 1, 3, etc.
```

**1 variation**: 4 total (fastest, less exploration)
**2 variations**: 8 total (balanced)
**3 variations**: 12 total (more exploration)

---

## Monitoring

### Watch throttling in action
```bash
tail -f worker2.log | grep "⏸️.*skipping"
# Output: ⏸️  Worker 5 skipping 'ProjectName - Escalation L2' - 3 workers already on 'ProjectName'
```

### Check active base project counts
```bash
python3 << 'EOF'
import sys; sys.path.insert(0, '/home/pi/Desktop/test/create')
from worker2 import ACTIVE_BASE_PROJECTS
print("Active base projects:", ACTIVE_BASE_PROJECTS)
EOF
```

### Verify variation counts
```bash
grep "Escalation L" ideas_log.json | wc -l  # Should be multiple of 8
```

---

## Expected Behavior

**Healthy operation**:
- Fresh projects process immediately (7-10 workers active)
- Failed projects get 3 retry attempts concurrently
- Escalations requeue after throttle → processed when slots free
- No more queue-wide stalls

**Logs to watch for**:
- `⏸️  Worker X skipping ... - 3 workers already on ...` (throttle working)
- `✅ Worker X finished ProjectName` (successful completion)
- Multiple different projects in worker status (diverse processing)

---

## Summary

✅ **Throttling Active**:
- Max 3 workers per base project
- 8 escalation variations (down from 20)
- Priority-based requeuing
- 70% more workers available for fresh projects

System now processes diverse projects instead of flooding with retry variations.
