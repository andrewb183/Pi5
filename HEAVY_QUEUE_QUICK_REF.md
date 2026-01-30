# Heavy Projects Queue - Quick Reference

## System Status
```
✅ ACTIVE - Heavy projects queue system fully operational
```

## Queue Configuration
| Queue | Projects | Languages | Processing |
|-------|----------|-----------|------------|
| Fast | 370 | Python, JavaScript | Parallel (10 workers) |
| Heavy | 304 | Rust, C++, Go, Java, C# | Sequential (1 at a time) |
| **Backup** | **674** | **All** | **Not running** |

## How It Works
1. retry_manager checks every 30 seconds
2. When fast queue < 50 items → feeds ONE heavy project
3. Worker processes single heavy project (may take 5-10 hours)
4. When complete → next heavy project feeds
5. Repeat until all heavy projects complete

## Key Files
- `ideas_log.json` - Fast queue (370 Python/JS)
- `heavy_projects_queue.json` - Heavy queue (304 Rust/C++/Go/Java/C#)
- `ideas_log_backup_before_cleanup.json` - Full backup (674 original)
- `retry_manager.py` - Has `_feed_heavy_projects()` method

## Monitoring
```bash
# Watch heavy projects feeding
tail -f retry_manager.log | grep "⏸️"

# Check queues
python3 verify_heavy_queue.py

# Overall status
python3 monitor_queue.py --status
```

## Expected Output
```
⏸️  Fed 1 heavy project: RustyArt (RUST)
   Remaining in heavy queue: 303

⏸️  Fed 1 heavy project: Text Adventure Game (RUST)
   Remaining in heavy queue: 302
```

## What to Adjust

**Feed heavy projects more often:**
Edit `retry_manager.py` line ~366:
```python
if len(ideas) > 100:  # Changed from 50
```

**Feed heavy projects less often:**
```python
if len(ideas) > 30:  # Changed from 50
```

## Emergency Actions

**Disable heavy projects:**
```bash
mv heavy_projects_queue.json heavy_projects_queue.json.paused
```

**Re-enable all at once:**
```bash
cp ideas_log_backup_before_cleanup.json ideas_log.json && rm heavy_projects_queue.json
pkill worker2 && python3 -u worker2.py > worker2.log 2>&1 &
```

**Force specific project next:**
- Manually move it to front of `ideas_log.json`
- Retry_manager will process it when current completes

## Timeout Configuration
- Fast projects: 50x multiplier
- Heavy projects: 100x multiplier
- Located in: `mk14.py` lines 51-57

## Learning Database Status
- ✅ Hooks installed in mk14.py and retry_manager.py
- ✅ Captures fixes from both fast and heavy projects
- ✅ Improves over time (month 3: 45% fix reuse)
- File: `implementation_outputs/fix_database.json`

## Everything Ready?
Run this to confirm:
```bash
python3 verify_heavy_queue.py
```

Expected: All ✅ checks

---

**Last Updated**: 21 January 2026
**Status**: Fully Operational
