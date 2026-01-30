#!/usr/bin/env python3
"""
Clean up timeout-prone projects from the ideas queue

Separates heavy language projects (Rust/C++/Go/Java/C#) into a separate queue.
They will only run when the main queue is empty, one at a time.
"""

import json
from pathlib import Path

ideas_file = Path('ideas_log.json')
heavy_queue_file = Path('heavy_projects_queue.json')

if not ideas_file.exists():
    print("❌ ideas_log.json not found")
    exit(1)

# Load ideas
with open(ideas_file) as f:
    ideas = json.load(f)

print(f"📋 Current queue: {len(ideas)} ideas")
print()

# Identify timeout-prone languages
timeout_prone = ['rust', 'c++', 'go', 'java', 'c#']

# Separate ideas
keep = []
heavy = []

for idea in ideas:
    lang = idea.get('language', 'Python').lower()
    title = idea.get('title', 'Unknown')
    
    if lang in timeout_prone:
        heavy.append(idea)
    else:
        keep.append(idea)

print(f"🎯 Timeout-prone (heavy) languages found:")
lang_counts = {}
for idea in heavy:
    lang = idea.get('language', 'Python').lower()
    lang_counts[lang] = lang_counts.get(lang, 0) + 1

for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
    print(f"  - {lang.upper()}: {count} projects")

print()
print(f"📦 Moving {len(heavy)} heavy projects to separate queue (run one-at-a-time)...")
print(f"✅ Keeping {len(keep)} fast projects (Python/JavaScript) for main queue")

# Show examples
print("\nExamples of heavy projects (will run when queue is empty):")
for idea in heavy[:10]:
    lang = idea.get('language', 'Unknown').upper()
    title = idea.get('title', 'Unknown')
    print(f"  ⏸️  {title} ({lang})")
if len(heavy) > 10:
    print(f"  ... and {len(heavy) - 10} more")

# Backup original
backup_file = Path('ideas_log_backup_before_cleanup.json')
if not backup_file.exists():
    with open(backup_file, 'w') as f:
        json.dump(ideas, f, indent=2)
    print(f"\n💾 Full backup saved to {backup_file}")

# Save fast queue
with open(ideas_file, 'w') as f:
    json.dump(keep, f, indent=2)

# Save heavy queue
with open(heavy_queue_file, 'w') as f:
    json.dump(heavy, f, indent=2)

print(f"\n✅ Queue separated!")
print(f"   Fast projects: {len(keep)} in ideas_log.json")
print(f"   Heavy projects: {len(heavy)} in {heavy_queue_file}")
print(f"\n🚀 Main queue will prioritize fast projects")
print(f"⏸️  Heavy projects run one-at-a-time when main queue empties")
print(f"   (retry_manager checks and feeds them automatically)")

