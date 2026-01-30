# Error Logging & Retry System - Complete Documentation

## Overview

The system now has comprehensive error logging and automatic retry capabilities optimized for old hardware.

## ✅ What's New

### 1. **Error Logging System**
All errors during code generation are now logged to `/implementations/error_log.json`:

```json
{
  "project_dir": "/path/to/project",
  "title": "Project Name",
  "language": "Python",
  "error_type": "compilation",
  "error_message": "SyntaxError: invalid syntax",
  "timestamp": "2026-01-13T...",
  "retry_count": 0,
  "details": {
    "traceback": "Full stack trace...",
    "line": 42
  }
}
```

### 2. **Automatic Retry Queue**
Failed projects are added to `/implementations/retry_queue.json` for automatic reattempt:

```json
{
  "project_dir": "/path/to/project",
  "title": "Project Name", 
  "description": "Description...",
  "language": "Python",
  "error_type": "test_syntax",
  "last_error": "Error message...",
  "first_attempt": "2026-01-13T...",
  "last_attempt": "2026-01-13T...",
  "retry_count": 1,
  "priority": "high"
}
```

### 3. **Hardware-Optimized Timeouts**

**All timeouts increased 10x for old hardware:**

| Operation | Old Timeout | New Timeout |
|-----------|-------------|-------------|
| Python execution | 5s | 50s |
| JavaScript execution | 5s | 50s |
| Java compilation | 10s | 100s |
| Java execution | 5s | 50s |
| C++ compilation | 15s | 150s |
| C++ execution | 5s | 50s |
| C# dotnet build | 30s | 300s (5min) |
| C# execution | 5s | 50s |
| Go compilation+run | 10s | 100s |
| Rust compilation | 30s | 300s (5min) |
| Rust execution | 5s | 50s |
| API requests | 30s | 300s (5min) |
| Port checks | 1.5s | 15s |
| Health checks | 3s | 30s |

**Configurable via environment variable:**
```bash
export MK14_TIMEOUT_MULTIPLIER=10  # Default
export MK14_TIMEOUT_MULTIPLIER=20  # Even slower hardware
```

### 4. **Error Types Tracked**

- `implementation` - Full implementation failure
- `test_syntax` - Syntax errors during testing
- `test_compilation` - Compilation failures
- `test_runtime` - Runtime errors during execution
- `test_execution` - General execution failures
- `no_compiler` - Missing compiler/interpreter (not retried)

## 📋 Files Modified

### `/home/pi/Desktop/test/create/mk14.py`

**Changes:**
1. Added error logging paths: `error_log_path`, `retry_queue_path`
2. Added timeout multiplier configuration (default 10x)
3. New method: `_log_error()` - Log errors to error_log.json
4. New method: `_add_to_retry_queue()` - Queue failed projects for retry
5. Updated `implement()` - Wrapped in try/except with error logging
6. Updated `_test_code()` - Logs test failures to retry queue
7. All timeouts increased 10x:
   - Python: 5s → 50s
   - JavaScript: 5s → 50s
   - Java: 10s → 100s (compile), 5s → 50s (run)
   - C++: 15s → 150s (compile), 5s → 50s (run)
   - C#: 30s → 300s (build), 5s → 50s (run)
   - Go: 10s → 100s
   - Rust: 30s → 300s (compile), 5s → 50s (run)
   - API: 30s → 300s

### `/home/pi/Desktop/test/create/process_retry_queue.py` (NEW)

**Purpose:** Automatically process retry queue and reattempt failed projects

**Features:**
- Loads retry_queue.json
- Sorts by priority (high first) and retry count
- Maximum 3 retry attempts per project
- Different retry strategies per error type:
  - `test_*` - Re-run tests with extended timeouts
  - `compilation` - Retry compilation
  - `implementation` - Full re-implementation via mk14
- Updates retry counts and timestamps
- Removes successful fixes from queue
- Marks abandoned projects after 3 failed retries

**Usage:**
```bash
# Process default retry queue
python3 process_retry_queue.py

# Process custom queue
python3 process_retry_queue.py /path/to/retry_queue.json
```

## 🚀 Usage Examples

### 1. Normal Operation (Automatic Error Logging)

```bash
# Errors are automatically logged during mk14 execution
python3 mk14.py '{"title":"My App","code":"print(hello)","language":"Python"}'

# If it fails, check the logs:
cat implementations/error_log.json
cat implementations/retry_queue.json
```

### 2. Process Retry Queue

```bash
cd /home/pi/Desktop/test/create
python3 process_retry_queue.py
```

**Output:**
```
🔄 Processing Retry Queue
============================================================
📋 Found 5 items in retry queue

1. calculator_app
   Language: Python
   Error: test_syntax - SyntaxError: invalid syntax
   Retry count: 0/3
   Priority: high
   🔄 Retrying python test...
   ✅ Successfully fixed!

2. web_scraper
   Language: Python
   Error: test_runtime - ImportError: No module named 'requests'
   Retry count: 1/3
   Priority: high
   🔄 Retrying python test...
   ❌ Retry failed

============================================================
📊 Retry Queue Processing Summary
============================================================
Processed: 5
✅ Fixed: 2
❌ Failed: 3
📋 Remaining in queue: 3
```

### 3. Check Error Logs

```bash
# View all errors
cat implementations/error_log.json | jq .

# View retry queue
cat implementations/retry_queue.json | jq .

# Count errors by type
cat implementations/error_log.json | jq -r '.[].error_type' | sort | uniq -c
```

### 4. Monitor Retry Queue Over Time

```bash
# Watch retry queue (updates every 2 seconds)
watch -n 2 'cat implementations/retry_queue.json | jq "length"'

# Automated retry processing (every 10 minutes)
while true; do
    python3 process_retry_queue.py
    sleep 600
done
```

## 🔧 Configuration

### Environment Variables

```bash
# Timeout multiplier for old hardware (default: 20)
export MK14_TIMEOUT_MULTIPLIER=20

# Max parallel model queries (default: 4)
export MK14_MAX_PARALLEL_QUERIES=4
```

### Retry Queue Settings

Edit `process_retry_queue.py`:

```python
class RetryProcessor:
    def __init__(self, retry_queue_path="./implementations/retry_queue.json"):
        self.retry_queue_path = Path(retry_queue_path)
        self.max_retries = 3  # Change to 5 for more attempts
        ...
```

## 📊 Monitoring & Reporting

### Error Log Statistics

```bash
# Total errors logged
cat implementations/error_log.json | jq 'length'

# Errors by type
cat implementations/error_log.json | jq -r '.[].error_type' | sort | uniq -c

# Recent errors (last 5)
cat implementations/error_log.json | jq '.[-5:]'

# Errors for specific project
cat implementations/error_log.json | jq '.[] | select(.title=="calculator_app")'
```

### Retry Queue Statistics

```bash
# Projects in retry queue
cat implementations/retry_queue.json | jq 'length'

# By priority
cat implementations/retry_queue.json | jq 'group_by(.priority) | map({priority: .[0].priority, count: length})'

# By retry count
cat implementations/retry_queue.json | jq 'group_by(.retry_count) | map({retries: .[0].retry_count, count: length})'

# High priority items
cat implementations/retry_queue.json | jq '.[] | select(.priority=="high")'
```

## 🎯 Error Priority System

**High Priority (immediate retry):**
- `compilation` - Code won't compile
- `test_syntax` - Syntax errors
- `test_runtime` - Runtime errors
- `implementation` - Full implementation failure

**Normal Priority (lower urgency):**
- `test_execution` - General execution issues
- `test_timeout` - Timeouts (may just need more time)

**Not Retried:**
- `no_compiler` - Missing compiler/interpreter (fix system first)

## ✅ Benefits

1. **No Lost Work** - All failures are logged, nothing is forgotten
2. **Automatic Recovery** - Failed projects get automatic retry attempts
3. **Smart Prioritization** - High-priority errors fixed first
4. **Hardware-Friendly** - 10x longer timeouts prevent false failures on old hardware
5. **Transparent** - Full error logs with tracebacks for debugging
6. **Configurable** - Adjust timeouts and retry counts as needed

## 🔄 Workflow

```
┌─────────────────────┐
│  mk14 starts        │
│  implementation     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Error occurs       │
└──────────┬──────────┘
           │
           ├─────────────────────┐
           │                     │
           ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐
│  Log to             │  │  Add to             │
│  error_log.json     │  │  retry_queue.json   │
└─────────────────────┘  └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  User runs          │
                         │  process_retry_     │
                         │  queue.py           │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌──────────┐    ┌──────────┐    ┌──────────┐
            │ Success  │    │  Failed  │    │  Max     │
            │ (remove  │    │ (retry   │    │  retries │
            │  from    │    │  +1,     │    │ (mark    │
            │  queue)  │    │  keep in │    │  abandon)│
            └──────────┘    │  queue)  │    └──────────┘
                           └──────────┘
```

## 📝 Example Error Log Entry

```json
{
  "project_dir": "/home/pi/Desktop/test/create/implementations/calculator_app",
  "title": "calculator_app",
  "language": "Python",
  "error_type": "test_syntax",
  "error_message": "invalid syntax (<string>, line 42)",
  "timestamp": "2026-01-13T10:30:45.123456",
  "retry_count": 0,
  "details": {
    "traceback": "Traceback (most recent call last):\n  File \"...\", line 42\n    print(\"Result:\" result)\n                    ^\nSyntaxError: invalid syntax",
    "idea_title": "calculator_app",
    "language": "Python",
    "type": "syntax",
    "line": 42
  }
}
```

## 🎉 Summary

The system is now fully equipped with:
- ✅ Comprehensive error logging
- ✅ Automatic retry queue
- ✅ Hardware-optimized timeouts (10x increase)
- ✅ Smart prioritization
- ✅ Automated retry processing
- ✅ Full traceability

**No errors are lost, and everything gets a chance to be fixed automatically!**
