# Heavy Projects Queue Setup

## Overview
Heavy language projects (Rust, C++, Go, Java, C#) are now managed in a separate queue that runs **one-at-a-time** when the main queue is empty.

## How It Works

### Queue Structure
- **Main Queue** (`ideas_log.json`): 370 fast projects (Python, JavaScript)
- **Heavy Queue** (`heavy_projects_queue.json`): 304 heavy projects (Rust, C++, Go, Java, C#)

### Automatic Feeding Logic
`retry_manager.py` automatically feeds heavy projects when:
1. Main queue drops below 50 ideas
2. Takes exactly ONE project from heavy queue
3. Adds it to ideas_log.json
4. Removes it from heavy_projects_queue.json

### Timeline
```
Heavy Queue: [RustyArt, Text Adventure, Image Grading, ...]
                        ↓ (when main queue < 50)
                [RustyArt added to main queue]
                        ↓ (processes)
                [RustyArt moved to Desktop]
                        ↓ (when main queue < 50 again)
                [Text Adventure added to main queue]
                        ... continues
```

## Configuration

**File**: `retry_manager.py` lines ~366-380

```python
def _feed_heavy_projects(self):
    """Feed one heavy project when main queue is empty."""
    # Only feed if main queue < 50 items
    if len(ideas) > 50:
        return
    
    # Take ONE heavy project
    heavy_project = heavy_projects.pop(0)
    ideas.append(heavy_project)
```

**Threshold**: 50 ideas in main queue
- **Why**: Ensures fast projects always available
- **Adjustable**: Edit line in `_feed_heavy_projects()` method

## Monitoring

### Check Heavy Queue Status
```bash
# Count remaining heavy projects
jq 'length' heavy_projects_queue.json

# See which heavy projects are queued
jq '.[] | {title, language}' heavy_projects_queue.json | head -20
```

### Watch Heavy Projects Being Added
```bash
# Monitor retry_manager output
tail -f retry_manager.log | grep "⏸️"
```

Example output:
```
⏸️  Fed 1 heavy project: RustyArt (RUST)
   Remaining in heavy queue: 303
```

### See Processing
```bash
# Monitor when heavy projects complete
tail -f /home/pi/Desktop/monitor_* | grep -E "RUST|C\+\+|GO|JAVA|C#"
```

## Benefits

✅ **No more timeouts blocking fast projects**
- Fast Python/JS projects process continuously
- Heavy compilations don't starve the queue

✅ **Predictable resource usage**
- Only ONE heavy project at a time
- Prevents RAM/CPU spikes

✅ **Learning database continues**
- Escalation system still active
- Fixes learned from all languages

✅ **No projects lost**
- Backup: `ideas_log_backup_before_cleanup.json` (674 original ideas)
- Heavy projects: `heavy_projects_queue.json` (304 projects)
- Fast projects: `ideas_log.json` (370 projects)

## Managing the Queues

### Re-enable all projects at once
```bash
# Restore full queue
cp ideas_log_backup_before_cleanup.json ideas_log.json
rm heavy_projects_queue.json

# Restart
pkill worker2 && python3 -u worker2.py > worker2.log 2>&1 &
```

### Add projects manually to heavy queue
```bash
python3 -c "
import json
heavy = json.load(open('heavy_projects_queue.json'))
heavy.append({'title': 'MyProject', 'language': 'Rust', ...})
json.dump(heavy, open('heavy_projects_queue.json', 'w'), indent=2)
"
```

### Check processing speed
```bash
# Fast queue (should be < 1 hour each)
ls -1 /home/pi/Desktop/*Python* | wc -l

# Slow queue (may take 5-10 hours each)
ls -1 /home/pi/Desktop/*Rust* | wc -l
```

## When to Adjust

### Increase threshold (currently 50)
**Edit**: `retry_manager.py` line ~366
```python
if len(ideas) > 50:  # Change to 100 or 150
```
- **Pro**: Feeds heavy projects more often
- **Con**: Fast queue may stall waiting for compilations

### Decrease threshold
```python
if len(ideas) > 20:  # More aggressive, more frequent heavy projects
```
- **Pro**: Heavy projects progress faster
- **Con**: Fast projects may timeout if too many heavy in flight

## Current Status

```
✅ Heavy Queue Separation: ACTIVE
📋 Main Queue: 370 fast projects
⏸️  Heavy Queue: 304 projects
🚀 Auto-feeding: ENABLED (threshold: 50 ideas)
🔄 One-at-a-time: ENFORCED per heavy project
```

## Troubleshooting

**Q: Heavy projects not feeding even though main queue is small?**
A: Check `heavy_projects_queue.json` exists and isn't empty
```bash
ls -lh heavy_projects_queue.json
jq 'length' heavy_projects_queue.json
```

**Q: Too many heavy projects processing at once?**
A: The `_feed_heavy_projects()` method only feeds ONE per cycle
- Check if multiple are in main queue already
- Wait for current to complete before next feeds

**Q: Want to immediately process a heavy project?**
A: Manually move it to ideas_log.json (front of queue):
```bash
python3 -c "
import json

# Load queues
ideas = json.load(open('ideas_log.json'))
heavy = json.load(open('heavy_projects_queue.json'))

# Move specific project
project = [p for p in heavy if 'RustyArt' in p['title']][0]
heavy.remove(project)
ideas.insert(0, project)  # Add to front

# Save
json.dump(ideas, open('ideas_log.json', 'w'), indent=2)
json.dump(heavy, open('heavy_projects_queue.json', 'w'), indent=2)
"
```
