#!/usr/bin/env python3
import asyncio
import json
import os
import gc
from pathlib import Path
from itertools import count
import time
from tempfile import NamedTemporaryFile
from tqdm import tqdm
import psutil  # optional: monitor RAM
import requests  # health pings
import socket
import subprocess
import fcntl  # file locking
import signal
import sys

from mk14 import CodeImplementer as Mk14Implementer

# Import escalating retry system for incomplete code handling
try:
    from escalating_retry_system import escalate_retry_for_project, LearningFixDatabase
    HAS_ESCALATION = True
except ImportError:
    HAS_ESCALATION = False
    tqdm.write("⚠️  escalating_retry_system not available - incomplete code will use basic routing")

# -------------------- Config --------------------
NUM_WORKERS = 10                      # concurrent mk14 runs (increased for speed) - OPTIMIZED: 6→10
JOB_QUEUE = asyncio.PriorityQueue(maxsize=20)  # priority queue for fast tasks (Python/JS with full testing)
SLOW_QUEUE = asyncio.PriorityQueue(maxsize=50)  # secondary queue for heavy-processing tasks (non-Python/JS or heavy healing)
SLOW_TASK_LOCK = asyncio.Lock()                 # serialize slow tasks
IMPLEMENTATIONS_DIR = "./implementations"  # where JSON tasks land
OUTPUT_PROJECT_DIR = "./implementation_outputs"  # where mk14 writes temp projects
RAM_THRESHOLD_MB = 16000              # optional: max RAM before pausing queue
CHECK_RAM_INTERVAL = 1                # seconds
IDEAS_LOG_PATH = Path(__file__).with_name("ideas_log.json")
QA_ISSUE_PATH = Path(__file__).with_name("QAissue.json")
INCOMPLETE_CODE_LOG = Path(__file__).with_name("incomplete_code_log.json")  # log broken code for fixing
IDLE_GRACE_SECONDS = 10               # seconds to wait after queue is empty before shutting down

# Per-language timeout configuration (in seconds)
# Fast languages get 5-10 min caps; heavy get 30-120 min
LANGUAGE_TIMEOUT_SECONDS = {
    "python": 10 * 60,        # 10 minutes - fast, test-friendly
    "javascript": 10 * 60,    # 10 minutes - fast, test-friendly
    "go": 30 * 60,            # 30 minutes - moderate compilation
    "c#": 45 * 60,            # 45 minutes - .NET builds can be slow
    "java": 45 * 60,          # 45 minutes - JVM startup + compilation
    "c++": 60 * 60,           # 60 minutes - heavy template instantiation + linking
    "rust": 120 * 60,         # 120 minutes (2h) - Rust is slowest on Pi
}
WORKER_TIMEOUT_SECONDS = 20 * 60     # 20 minutes - fallback default

IDEA_LOG_LOCK = asyncio.Lock()
QA_ISSUE_LOCK = asyncio.Lock()
INCOMPLETE_LOG_LOCK = asyncio.Lock()  # lock for incomplete code log
SEQ = count()  # monotonic sequence to break priority ties
WORKER_TASKS = {}                     # track worker asyncio tasks for timeout management
STATUS_FILE = Path(__file__).with_name("worker2_status.json")  # queue status for monitoring
IDEAS_LOG_LAST_SIZE = 0               # track number of ideas processed (count)
QA_ISSUE_LAST_SIZE = 0               # track number of QA issues processed (count)
IDEAS_LOG_LAST_MTIME = 0             # track file modification time for polling
QA_ISSUE_LAST_MTIME = 0              # track file modification time for polling

# Escalating retry system initialization
LEARNING_DB = LearningFixDatabase() if HAS_ESCALATION else None  # track learned fixes

# Model health + prioritization
MODEL_PORTS = {
    "qwen2.5-coder": [11435],
    "deepseek-r1": [11437],
}
# Initialize as True - will be checked by monitor_models()
MODEL_HEALTH = {"qwen2.5-coder": True, "deepseek-r1": True}
PREFERRED_MODEL = None  # set to "deepseek-r1" when it becomes healthy

# Concurrency throttling for same-project escalations
# Track how many workers are currently processing variations of the same base project
ACTIVE_BASE_PROJECTS = {}  # {base_project_name: count}
MAX_CONCURRENT_SAME_PROJECT = 3  # Max 3 workers on same failed project

# Worker status tracking for monitor
WORKER_STATUS = {
    i: {
        "status": "idle",
        "task": None,
        "started_at": None,
        "preferred_model": None,
        "language": "python",  # Track task language for per-language timeout
        "last_completed": None,
    }
    for i in range(NUM_WORKERS)  # Initialize for all workers (6, not 2)
}


async def _is_port_open(port: int, timeout: float = 1.5) -> bool:
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: _sync_port_check(port, timeout))
    except Exception:
        return False


def _sync_port_check(port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=timeout):
            return True
    except Exception:
        return False



async def _ping_model(model: str, port: int) -> bool:
    try:
        loop = asyncio.get_running_loop()
        def _req():
            return requests.post(
                f"http://localhost:{port}/api/generate",
                json={"model": model, "prompt": "ping", "stream": False, "options": {"num_predict": 1}},
                timeout=5,
            )
        resp = await loop.run_in_executor(None, _req)
        return resp.status_code == 200
    except Exception:
        return False


def select_model_for_worker(worker_id: int):
    """Assign models per worker.

    worker0: deepseek-r1 if healthy else qwen
    worker1+: qwen if healthy else deepseek
    """
    deepseek_ok = MODEL_HEALTH.get("deepseek-r1")
    qwen_ok = MODEL_HEALTH.get("qwen2.5-coder")

    if worker_id == 0:
        if deepseek_ok:
            return "deepseek-r1"
        if qwen_ok:
            return "qwen2.5-coder"
        return None

    # others prefer qwen
    if qwen_ok:
        return "qwen2.5-coder"
    if deepseek_ok:
        return "deepseek-r1"
    return None


def get_timeout_for_language(language: str) -> int:
    """Get per-language timeout in seconds.
    
    Fast languages (Python/JS) get 10 min; heavy get 30-120 min.
    """
    lang_lower = language.lower() if language else "python"
    return LANGUAGE_TIMEOUT_SECONDS.get(lang_lower, WORKER_TIMEOUT_SECONDS)



def update_status_file():
    """Write current queue and worker status to file for monitor."""
    try:
        # Get queue items (can't iterate PriorityQueue directly, so approximate)
        status_data = {
            "timestamp": time.time(),
            "queue_size": JOB_QUEUE.qsize(),
            "slow_queue_size": SLOW_QUEUE.qsize(),
            "workers": WORKER_STATUS.copy(),
            "model_health": MODEL_HEALTH.copy(),
            "preferred_model": PREFERRED_MODEL
        }
        _write_atomic_json(STATUS_FILE, status_data)
    except Exception:
        pass  # Don't crash if status update fails


def _write_atomic_json(path: Path, data):
    """Atomic JSON write: temp file then replace (avoids corruption)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".tmp") as tmp:
        # Lock the temp file during write
        fcntl.flock(tmp.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_name = tmp.name
        finally:
            fcntl.flock(tmp.fileno(), fcntl.LOCK_UN)
    os.replace(temp_name, path)


def _read_json_locked(path: Path, default=None):
    """Read JSON file with exclusive lock to prevent concurrent access corruption."""
    if not path.exists():
        return default if default is not None else []
    
    try:
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        tqdm.write(f"⚠️ Error reading {path}: {e}")
        return default if default is not None else []


async def _atomic_update_json(path: Path, lock: asyncio.Lock, update_fn):
    """Threaded atomic update of a JSON file guarded by an asyncio lock."""
    async with lock:
        def _update():
            try:
                current = _read_json_locked(path, [])
                new_data = update_fn(current)
                _write_atomic_json(path, new_data)
                return None
            except Exception as e:
                return e

        err = await asyncio.to_thread(_update)
        if err:
            raise err


def detect_incomplete_code(code: str, language: str) -> bool:
    """Detect if code has TODO/unfinished markers indicating incomplete generation.
    
    Returns True if code is incomplete and should be flagged for regeneration.
    """
    if not code:
        return False
    
    incomplete_markers = [
        "# TODO",
        "// TODO",
        "/* TODO",
        "# FIXME",
        "// FIXME",
        "Complete implementation",
        "based on title requirements",
        "Your implementation here",
        "Add your code here",
        "SyntaxError:",  # Generated code with syntax errors
    ]
    
    code_lower = code.lower()
    for marker in incomplete_markers:
        if marker.lower() in code_lower:
            return True
    
    return False


async def log_incomplete_code(idea: dict, code: str, error_msg: str = ""):
    """Log incomplete/broken code to incomplete_code_log.json for manual review and fix attempts."""
    async def _log(current):
        entry = {
            "title": idea.get("title", "Unknown"),
            "language": idea.get("language", "unknown"),
            "detected_at": time.time(),
            "error": error_msg,
            "code_preview": code[:200] if code else "",  # First 200 chars
            "code_length": len(code) if code else 0,
            "retry_count": idea.get("retry_count", 0),
        }
        
        # Add to log
        if not isinstance(current, list):
            current = []
        
        # Check if already logged
        existing = [e for e in current if e.get("title") == entry["title"]]
        if not existing:
            current.append(entry)
            tqdm.write(f"📋 Logged incomplete code for '{entry['title']}' - will attempt regeneration")
        
        return current
    
    try:
        await _atomic_update_json(INCOMPLETE_CODE_LOG, INCOMPLETE_LOG_LOCK, _log)
    except Exception as e:
        tqdm.write(f"⚠️ Could not log incomplete code: {e}")


async def route_to_regeneration(idea: dict, code: str, error_msg: str):
    """Route incomplete code through escalating retry system for intelligent regeneration.
    
    Uses 4-level escalation (Conservative → Moderate → Aggressive → Nuclear)
    with 20 prompt variations and learning database for smart fixes.
    """
    project_title = idea.get("title", "Unknown")
    
    # Try escalating retry system if available
    if HAS_ESCALATION and LEARNING_DB:
        try:
            # STEP 1: Run root cause analysis to identify fundamental issues
            try:
                from root_cause_analyzer import analyze_and_report
                
                analysis_result = analyze_and_report(idea, error_msg)
                
                if analysis_result['has_fundamental_issues']:
                    tqdm.write(f"🔍 Root cause analysis found {analysis_result['issue_count']} fundamental issues:")
                    for issue in analysis_result['issues']:
                        tqdm.write(f"  - [{issue['severity'].upper()}] {issue['type']}: {issue['description']}")
                    tqdm.write(f"  → Recommended: {analysis_result['recommended_action']}")
                    
                    # Add analysis to error log
                    error_msg_enhanced = f"{error_msg}\n\nROOT CAUSE ANALYSIS:\n"
                    for instruction in analysis_result['fix_instructions']:
                        error_msg_enhanced += f"{instruction}\n"
                else:
                    error_msg_enhanced = error_msg
            except Exception as e:
                tqdm.write(f"⚠️ Root cause analysis failed: {e}")
                error_msg_enhanced = error_msg
            
            # STEP 2: Escalate with enhanced context
            tqdm.write(f"📈 Escalating '{project_title}' through 4-level strategy with root cause fixes...")
            
            # Prepare error log for escalation context
            error_log = [
                {
                    "type": "incomplete_code",
                    "message": error_msg_enhanced,
                    "code_length": len(code),
                    "detected_at": time.time(),
                }
            ]
            
            # STEP 3: Integrate think mode for aggressive escalation levels
            try:
                from think_mode_escalation import ThinkModeEscalation
                
                think_mode = ThinkModeEscalation()
                has_critical = any(i['severity'] == 'critical' for i in analysis_result.get('issues', []))
                
                # Mark escalated ideas with think mode preference
                escalation_meta = {
                    'use_think_mode_l3_l4': True,
                    'critical_issues_detected': has_critical,
                    'think_reason': 'Nuclear/Aggressive escalation with deep reasoning for broken code'
                }
                tqdm.write(f"  💭 Think mode enabled for L3-L4 (aggressive/nuclear escalation)")
            except Exception as e:
                tqdm.write(f"⚠️ Think mode integration failed: {e}")
                escalation_meta = {}
            
            # Use escalating retry system to generate 20 variations
            escalated_ideas = escalate_retry_for_project(
                project_title,
                error_log,
                idea,
                LEARNING_DB
            )
            
            if escalated_ideas:
                # Add escalated ideas to QA issue queue
                async def _add_escalated(current):
                    if not isinstance(current, list):
                        current = []
                    
                    for escalated_idea in escalated_ideas:
                        # Add think mode metadata
                        escalated_idea.update(escalation_meta)
                        
                        # Check if already in queue
                        if not any(i.get("title") == escalated_idea.get("title") for i in current):
                            current.append(escalated_idea)
                    
                    return current
                
                await _atomic_update_json(QA_ISSUE_PATH, QA_ISSUE_LOCK, _add_escalated)
                tqdm.write(f"✅ Created {len(escalated_ideas)} escalated variations for '{project_title}':")
                
                # Show escalation levels with think mode indicator
                levels = {}
                for esc_idea in escalated_ideas:
                    level = esc_idea.get("escalation_level", "Unknown")
                    levels[level] = levels.get(level, 0) + 1
                
                for level, count in sorted(levels.items()):
                    think_indicator = "💭" if level in ["Aggressive", "Nuclear"] else "  "
                    tqdm.write(f"   {think_indicator} {level}: {count} variations")
                
                return  # Success - escalation handled
        
        except Exception as e:
            tqdm.write(f"⚠️  Escalation failed: {e}, falling back to basic routing")
    
    # Fallback: Basic regeneration routing (no escalation)
    async def _route(current):
        if not isinstance(current, list):
            current = []
        
        # Create basic regeneration task
        regen_task = {
            "title": project_title,
            "description": f"REGENERATE: Incomplete code detected - {error_msg}",
            "code": code,
            "language": idea.get("language", "javascript"),
            "error_type": "incomplete_code",
            "last_error": f"Code contains TODO markers or syntax errors: {error_msg}",
            "first_attempt": time.time(),
            "last_attempt": time.time(),
            "retry_count": 0,
            "escalation_level": "basic_retry",  # Mark as non-escalated
        }
        
        # Add to QA issue queue
        current.append(regen_task)
        tqdm.write(f"🔄 Routed '{project_title}' to basic regeneration queue")
        
        return current
    
    try:
        await _atomic_update_json(QA_ISSUE_PATH, QA_ISSUE_LOCK, _route)
    except Exception as e:
        tqdm.write(f"⚠️ Could not route to regeneration: {e}")


def should_skip_completed(idea) -> bool:
    """Skip task if project_metadata.json on Desktop shows completed."""
    title = idea.get("title")
    if not title:
        return False
    project_name = title.replace(' ', '_').lower()
    desktop_dir = Path.home() / "Desktop"
    meta_path = desktop_dir / project_name / "project_metadata.json"
    try:
        if meta_path.exists():
            with open(meta_path, "r") as f:
                data = json.load(f)
                if data.get("status") == "completed":
                    tqdm.write(f"⏭️ Skipping completed project {title} (metadata found)")
                    return True
    except Exception:
        return False
    return False


def should_use_slow_queue(idea) -> bool:
    """Determine if task needs heavy processing (goes to SLOW_QUEUE).
    
    Tasks go to SLOW_QUEUE if:
    - Language is non-Python/JS (will skip heavy testing)
    - Task requires heavy healing (large projects, complex apps)
    
    Fast tasks (Python/JS) stay in main queue.
    """
    language = idea.get('language', 'Python').lower()
    code = idea.get('code', '')
    
    # Non-Python/JS languages skip testing, so they're lighter and go to slow queue
    if language not in ('python', 'javascript'):
        return True
    
    # Large code or complex-looking tasks might need heavy healing
    if len(code) > 2000:  # arbitrary threshold for "large"
        return True
    
    # Default: fast queue
    return False


async def update_status_periodically(interval: int = 30):
    """Periodically update status file to keep monitor fresh with live elapsed times."""
    while True:
        try:
            await asyncio.sleep(interval)
            update_status_file()
        except Exception:
            pass


async def monitor_worker_timeouts(interval: int = 30):
    """Monitor workers for timeout and restart them.
    
    Timeout is per-language:
    - Python/JS: 10 min
    - Go/C#/Java: 30-45 min
    - C++: 60 min
    - Rust: 120 min
    """
    while True:
        try:
            await asyncio.sleep(interval)
            current_time = time.time()
            
            for worker_id, status in WORKER_STATUS.items():
                if status['status'] == 'working' and status['started_at']:
                    elapsed = current_time - status['started_at']
                    task_name = status.get('task', 'Unknown')
                    language = status.get('language', 'python')
                    timeout_seconds = get_timeout_for_language(language)
                    
                    if elapsed > timeout_seconds:
                        tqdm.write(f"⏰ Worker {worker_id} TIMEOUT after {elapsed/60:.1f}min on '{task_name}' ({language})")
                        tqdm.write(f"   (limit: {timeout_seconds/60:.0f}min for {language})")

                        tqdm.write(f"   Cancelling stuck worker {worker_id}...")
                        
                        # Cancel the worker task
                        if worker_id in WORKER_TASKS:
                            WORKER_TASKS[worker_id].cancel()
                            tqdm.write(f"   ✓ Worker {worker_id} cancelled, will restart automatically")
                        
                        # Reset worker status
                        WORKER_STATUS[worker_id].update({
                            "status": "timeout_restart",
                            "task": None,
                            "started_at": None,
                            "preferred_model": None,
                            "last_completed": f"TIMEOUT: {task_name}",
                        })
                        update_status_file()
                        
        except Exception as e:
            tqdm.write(f"⚠️ Worker timeout monitor error: {e}")


async def monitor_models(interval: int = 5):
    """Periodically check model endpoints and adjust prioritization (faster 5s check).

    - Prints health status changes (OK/DOWN/BUSY)
    - Prefers deepseek-r1 when it becomes healthy
    - If port is open, model is healthy (skip expensive ping for speed)
    """
    global PREFERRED_MODEL
    while True:
        try:
            for model, ports in MODEL_PORTS.items():
                healthy = False
                for port in ports:
                    # Fast port check only (skip ping to avoid timeout delays)
                    port_ok = await _is_port_open(port)
                    if port_ok:
                        healthy = True
                        break

                prev = MODEL_HEALTH.get(model)
                MODEL_HEALTH[model] = healthy
                if prev is not None and prev != healthy:
                    status = "OK" if healthy else "DOWN"
                    tqdm.write(f"🩺 Model health: {model} → {status}")

            # Prefer deepseek when it is healthy
            if MODEL_HEALTH.get("deepseek-r1"):
                if PREFERRED_MODEL != "deepseek-r1":
                    PREFERRED_MODEL = "deepseek-r1"
                    tqdm.write("🎗 Prioritizing deepseek-r1 (worker0) while others use qwen")
                    await reprioritize_queue(new_priority=0)
            else:
                if PREFERRED_MODEL is not None:
                    PREFERRED_MODEL = None
                    tqdm.write("🎗 Preference cleared; both workers use qwen")
        except Exception as e:
            tqdm.write(f"⚠️ Model monitor error: {e}")
        finally:
            await asyncio.sleep(interval)


async def run_mk14_implementation(idea, worker_id, model_override=None, prune_after=True):
    """Run mk14's CodeImplementer in a thread to avoid blocking the event loop."""

    def _execute():
        idea_with_output = dict(idea)
        idea_with_output.setdefault("output_dir", OUTPUT_PROJECT_DIR)
        # Per-worker model preference: worker0 tries deepseek if healthy; worker1 uses qwen
        preferred = model_override or select_model_for_worker(worker_id)
        if preferred:
            idea_with_output["preferred_model"] = preferred
        impl = Mk14Implementer(idea_with_output)
        return impl.implement()

    result_path = await asyncio.to_thread(_execute)
    tqdm.write(
        f"✅ Worker {worker_id} finished {idea.get('title', 'unknown')}"
        + (f" [{model_override}]" if model_override else "")
        + f" → {result_path}"
    )
    
    # Check if generated code is incomplete
    code = idea.get("code", "")
    if detect_incomplete_code(code, idea.get("language", "javascript")):
        tqdm.write(f"⚠️ Detected incomplete code in '{idea.get('title', 'unknown')}' - logging for regeneration")
        await log_incomplete_code(idea, code, "Contains TODO markers or unfinished placeholders")
        await route_to_regeneration(idea, code, "Incomplete code generation - needs full regeneration")
        # DON'T prune - keep for retry
        return
    
    if prune_after:
        await prune_idea_from_log(idea.get("title"))


async def run_slow_task_twice(idea, worker_id, main_pbar, worker_pbar):
    """Process a slow task serially twice: deepseek-r1 then qwen2.5-coder."""
    async with SLOW_TASK_LOCK:
        models = ["deepseek-r1", "qwen2.5-coder"]
        worker_pbar.reset(total=len(models))
        last_completed_model = None

        for idx, model in enumerate(models):
            # Skip unhealthy model but continue to next
            if not MODEL_HEALTH.get(model):
                tqdm.write(f"⏭️ Skipping {model} for {idea.get('title')} (model unhealthy)")
                worker_pbar.update(1)
                continue

            # Update status for this model run
            WORKER_STATUS[worker_id].update(
                {
                    "status": "working",
                    "task": idea.get('title', 'Unknown'),
                    "started_at": time.time(),
                    "preferred_model": model,
                }
            )
            update_status_file()

            try:
                await run_mk14_implementation(
                    idea,
                    worker_id,
                    model_override=model,
                    prune_after=(idx == len(models) - 1),  # prune after final run
                )
                last_completed_model = model
            except Exception as e:
                tqdm.write(f"✗ Worker {worker_id} error on {model}: {e}")
            finally:
                worker_pbar.update(1)

        # Only count once on the main progress bar (task-level)
        main_pbar.update(1)

        # Reset status to idle after both passes
        WORKER_STATUS[worker_id].update(
            {
                "status": "idle",
                "task": None,
                "started_at": None,
                "preferred_model": None,
                "last_completed": f"{idea.get('title', 'Unknown')} [{last_completed_model or 'skipped'}]",
            }
        )
        update_status_file()


async def enqueue_task(idea, priority: int = 5):
    title = idea.get('title', 'unknown')
    
    if should_skip_completed(idea):
        tqdm.write(f"⏭️ Skipping completed: {title}")
        return
    
    # Route to appropriate queue
    if should_use_slow_queue(idea):
        try:
            await SLOW_QUEUE.put((priority, next(SEQ), idea))
            tqdm.write(f"📦 Task '{title}' → SLOW_QUEUE")
        except asyncio.QueueFull:
            tqdm.write(f"⚠️ SLOW_QUEUE full, skipping task: {title}")
    else:
        await JOB_QUEUE.put((priority, next(SEQ), idea))
        tqdm.write(f"📦 Task '{title}' → JOB_QUEUE")
    
    update_status_file()  # Update monitor on queue change


async def reprioritize_queue(new_priority: int = 0):
    """Drain and re-queue pending tasks with higher priority when deepseek recovers."""
    drained = []
    try:
        while True:
            item = JOB_QUEUE.get_nowait()
            drained.append(item)
    except asyncio.QueueEmpty:
        pass

    for _, _, idea in drained:
        await enqueue_task(idea, priority=new_priority)

    if drained:
        tqdm.write(f"🎗 Reprioritized {len(drained)} pending task(s) for deepseek-r1")


async def prune_idea_from_log(title):
    """Remove completed ideas from ideas_log.json to avoid repeats."""

    if not title:
        return

    async def _prune_file(path: Path, lock: asyncio.Lock):
        def _update(current):
            return [idea for idea in current if idea.get("title") != title]

        try:
            await _atomic_update_json(path, lock, _update)
            return True
        except Exception as e:
            tqdm.write(f"⚠️ Could not prune '{title}' from {path.name} ({e})")
            return False

    removed_main = await _prune_file(IDEAS_LOG_PATH, IDEA_LOG_LOCK)
    await _prune_file(QA_ISSUE_PATH, QA_ISSUE_LOCK)

    if removed_main:
        tqdm.write(f"🧹 Removed entries for '{title}' from queues")

# -------------------- Polling Functions (replaces file watchers) --------------------
# Using async polling instead of FSE watchers prevents race conditions that cause deadlock

async def poll_implementations_dir():
    """
    Poll implementations directory for new JSON files instead of using FSE.
    This prevents file watcher race conditions that cause deadlocks.
    """
    poll_interval = 3  # Check every 3 seconds
    processed_files = set()
    
    while True:
        try:
            await asyncio.sleep(poll_interval)
            if not Path(IMPLEMENTATIONS_DIR).exists():
                continue
            
            # Check for new JSON files
            json_files = list(Path(IMPLEMENTATIONS_DIR).glob("*.json"))
            for json_file in json_files:
                if json_file.name in processed_files:
                    continue
                if json_file.name == "rework_queue.json":
                    continue
                
                try:
                    # Load and enqueue
                    with open(json_file) as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        for task in data:
                            prio = 0 if PREFERRED_MODEL == "deepseek-r1" else 5
                            await enqueue_task(task, priority=prio)
                    else:
                        prio = 0 if PREFERRED_MODEL == "deepseek-r1" else 5
                        await enqueue_task(data, priority=prio)
                    
                    # Remove file after processing
                    try:
                        json_file.unlink()
                    except OSError:
                        pass
                    
                    tqdm.write(f"✅ Loaded tasks from {json_file.name}")
                    processed_files.add(json_file.name)
                    
                except Exception as e:
                    tqdm.write(f"❌ Failed to load {json_file.name}: {e}")
                    processed_files.add(json_file.name)
                    
        except Exception as e:
            tqdm.write(f"⚠️ Implementations dir polling error: {e}")
            await asyncio.sleep(5)


async def poll_ideas_log_changes():
    """
    Poll ideas_log.json for new entries instead of using FSE.
    This prevents file watcher race conditions that cause deadlocks.
    """
    global IDEAS_LOG_LAST_MTIME
    poll_interval = 2  # Check every 2 seconds
    
    while True:
        try:
            await asyncio.sleep(poll_interval)
            if not IDEAS_LOG_PATH.exists():
                continue
            
            # Check if file was modified (new ideas appended)
            try:
                current_mtime = IDEAS_LOG_PATH.stat().st_mtime
                if current_mtime != IDEAS_LOG_LAST_MTIME:
                    # File changed, reload it
                    await process_new_ideas_from_log()
                    IDEAS_LOG_LAST_MTIME = current_mtime
            except OSError:
                # File might be locked temporarily, skip this check
                pass
                
        except Exception as e:
            tqdm.write(f"⚠️ Ideas log polling error: {e}")
            await asyncio.sleep(5)


async def poll_qa_issues_changes():
    """
    Poll QAissue.json for new entries instead of using FSE.
    This prevents file watcher race conditions that cause deadlocks.
    """
    global QA_ISSUE_LAST_MTIME
    poll_interval = 2  # Check every 2 seconds
    
    while True:
        try:
            await asyncio.sleep(poll_interval)
            if not QA_ISSUE_PATH.exists():
                continue
            
            # Check if file was modified (new QA issues appended)
            try:
                current_mtime = QA_ISSUE_PATH.stat().st_mtime
                if current_mtime != QA_ISSUE_LAST_MTIME:
                    # File changed, reload it
                    await process_new_qa_issues_from_log()
                    QA_ISSUE_LAST_MTIME = current_mtime
            except OSError:
                # File might be locked temporarily, skip this check
                pass
                
        except Exception as e:
            tqdm.write(f"⚠️ QA issues polling error: {e}")
            await asyncio.sleep(5)


async def forced_periodic_reload():
    """
    Force a full reload of ideas_log.json and QAissue.json every 5 minutes.
    This catches changes that mtime-based polling misses due to filesystem timing issues.
    Prevents workers from going idle with a full backlog.
    """
    reload_interval = 5 * 60  # 5 minutes
    
    while True:
        try:
            await asyncio.sleep(reload_interval)
            
            # Forced full reload
            ideas = load_ideas_from_log()
            qa_issues = load_qa_issues_from_log()
            new_count = len(ideas) + len(qa_issues)
            
            if new_count > JOB_QUEUE.qsize() + SLOW_QUEUE.qsize():
                tqdm.write(f"🔄 Periodic reload: found {new_count - JOB_QUEUE.qsize() - SLOW_QUEUE.qsize()} new items, requeuing...")
                await enqueue_tasks(ideas)
                if qa_issues:
                    await enqueue_tasks(qa_issues)
                    
        except Exception as e:
            tqdm.write(f"⚠️ Forced reload error: {e}")
            await asyncio.sleep(30)


async def detect_stuck_workers():
    """
    Monitor for workers stuck idle with full queue.
    If all workers idle for >120s and ideas_log has >50 items, force a restart.
    """
    check_interval = 30  # Check every 30s
    last_active_time = time.time()
    
    while True:
        try:
            await asyncio.sleep(check_interval)
            
            # Count active workers
            active_count = sum(1 for w in WORKER_STATUS.values() if w.get('status') == 'working')
            ideas_count = 0
            if IDEAS_LOG_PATH.exists():
                ideas_count = len(json.loads(IDEAS_LOG_PATH.read_text()))
            
            if active_count == 0 and ideas_count > 50:
                elapsed = time.time() - last_active_time
                if elapsed > 120:
                    tqdm.write(f"🚨 Workers stuck idle for {elapsed:.0f}s with {ideas_count} ideas in queue!")
                    tqdm.write(f"🔄 Force-reloading queue...")
                    ideas = load_ideas_from_log()
                    qa_issues = load_qa_issues_from_log()
                    await enqueue_tasks(ideas)
                    if qa_issues:
                        await enqueue_tasks(qa_issues)
                    last_active_time = time.time()
            else:
                last_active_time = time.time()
                
        except Exception as e:
            tqdm.write(f"⚠️ Stuck detection error: {e}")
            await asyncio.sleep(30)


async def process_new_ideas_from_log():
    """Incrementally enqueue new ideas appended to ideas_log.json."""
    global IDEAS_LOG_LAST_SIZE
    try:
        async with IDEA_LOG_LOCK:
            if not IDEAS_LOG_PATH.exists():
                return
            ideas = await asyncio.to_thread(_read_json_locked, IDEAS_LOG_PATH, [])
            if not isinstance(ideas, list):
                return
            if len(ideas) <= IDEAS_LOG_LAST_SIZE:
                return
            new_items = ideas[IDEAS_LOG_LAST_SIZE:]
            IDEAS_LOG_LAST_SIZE = len(ideas)
            tqdm.write(f"ℹ️ Detected {len(new_items)} new ideas in ideas_log.json; enqueueing...")
            for idea in new_items:
                prio = 0 if PREFERRED_MODEL == "deepseek-r1" else 5
                await enqueue_task(idea, priority=prio)
    except Exception as e:
        tqdm.write(f"⚠️ Failed processing ideas_log.json update: {e}")


async def process_new_qa_issues_from_log():
    """Incrementally enqueue new QA issues appended to QAissue.json."""
    global QA_ISSUE_LAST_SIZE
    try:
        async with QA_ISSUE_LOCK:
            if not QA_ISSUE_PATH.exists():
                return
            issues = await asyncio.to_thread(_read_json_locked, QA_ISSUE_PATH, [])
            if not isinstance(issues, list):
                return
            if len(issues) <= QA_ISSUE_LAST_SIZE:
                return
            new_items = issues[QA_ISSUE_LAST_SIZE:]
            QA_ISSUE_LAST_SIZE = len(issues)
            tqdm.write(f"ℹ️ Detected {len(new_items)} new items in QAissue.json; enqueueing...")
            for issue in new_items:
                prio = 0 if PREFERRED_MODEL == "deepseek-r1" else 5
                await enqueue_task(issue, priority=prio)
    except Exception as e:
        tqdm.write(f"⚠️ Failed processing QAissue.json update: {e}")

# -------------------- Worker --------------------
async def worker(worker_id, main_pbar):
    worker_pbar = tqdm(
        total=0,
        position=worker_id + 1,
        desc=f"Worker {worker_id}",
        leave=False,
        bar_format="{desc} |{bar}| {percentage:3.0f}% [{elapsed}<{remaining}] {postfix}"
    )

    while True:
        try:
            # Check main queue first; only use slow queue if main is empty
            is_slow = False
            idea = None
            
            try:
                _, _, idea = JOB_QUEUE.get_nowait()
            except asyncio.QueueEmpty:
                # Main queue empty; try slow queue
                try:
                    _, _, idea = SLOW_QUEUE.get_nowait()
                    tqdm.write(f"📦 Worker {worker_id} processing from SLOW_QUEUE: {idea.get('title', 'unknown')}")
                    is_slow = True
                except asyncio.QueueEmpty:
                    # Both queues empty; wait for task
                    # Prefer main queue, but accept from slow queue if available
                    try:
                        _, _, idea = await asyncio.wait_for(JOB_QUEUE.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        try:
                            _, _, idea = await asyncio.wait_for(SLOW_QUEUE.get(), timeout=1.0)
                            tqdm.write(f"📦 Worker {worker_id} processing from SLOW_QUEUE: {idea.get('title', 'unknown')}")
                            is_slow = True
                        except asyncio.TimeoutError:
                            await asyncio.sleep(0.5)  # Idle sleep
                            continue
            
            # Check if too many workers are processing variations of the same base project
            base_project = idea.get('base_project_name') or idea.get('original_project')
            if base_project and base_project in ACTIVE_BASE_PROJECTS:
                concurrent_count = ACTIVE_BASE_PROJECTS[base_project]
                if concurrent_count >= MAX_CONCURRENT_SAME_PROJECT:
                    # Too many workers on this project; requeue and skip
                    tqdm.write(f"⏸️  Worker {worker_id} skipping '{idea.get('title')}' - {concurrent_count} workers already on '{base_project}'")
                    await asyncio.sleep(2)  # Brief delay before requeuing
                    await enqueue_task(idea, priority=idea.get('priority', 5))
                    try:
                        JOB_QUEUE.task_done()
                    except ValueError:
                        pass
                    try:
                        SLOW_QUEUE.task_done()
                    except ValueError:
                        pass
                    continue
            
            # Track this base project
            if base_project:
                ACTIVE_BASE_PROJECTS[base_project] = ACTIVE_BASE_PROJECTS.get(base_project, 0) + 1
            
            # Update worker status
            preferred = select_model_for_worker(worker_id)
            language = idea.get('language', 'python').lower()
            WORKER_STATUS[worker_id].update(
                {
                    "status": "working",
                    "task": idea.get('title', 'Unknown'),
                    "started_at": time.time(),
                    "preferred_model": preferred,
                    "language": language,  # Track language for timeout checking
                }
            )
            update_status_file()
            
            # mk14 is synchronous, so track as a single-step task (fast) or two-step (slow)
            worker_pbar.reset(total=2 if is_slow else 1)
            worker_pbar.set_postfix_str(f"{idea.get('title', 'Task')} ({idea.get('language', 'lang')})")

            try:
                # Only require a title; language defaults to Python/JS when missing.
                missing = [key for key in ("title",) if key not in idea]
                if missing:
                    tqdm.write(f"✗ Worker {worker_id} skipped task missing {missing}: {idea}")
                    worker_pbar.reset(total=0)
                    JOB_QUEUE.task_done() if hasattr(JOB_QUEUE, '_unfinished_tasks') else None
                    SLOW_QUEUE.task_done() if hasattr(SLOW_QUEUE, '_unfinished_tasks') else None
                    continue

                if is_slow:
                    await run_slow_task_twice(idea, worker_id, main_pbar, worker_pbar)
                else:
                    await run_mk14_implementation(idea, worker_id)
                    worker_pbar.update(1)
                    main_pbar.update(1)
            except Exception as e:
                tqdm.write(f"✗ Worker {worker_id} error: {e}")
            finally:
                # Release base project tracking
                base_project = idea.get('base_project_name') if idea else None
                if not base_project and idea:
                    base_project = idea.get('original_project')
                if base_project and base_project in ACTIVE_BASE_PROJECTS:
                    ACTIVE_BASE_PROJECTS[base_project] = max(0, ACTIVE_BASE_PROJECTS[base_project] - 1)
                    if ACTIVE_BASE_PROJECTS[base_project] == 0:
                        del ACTIVE_BASE_PROJECTS[base_project]
                
                gc.collect()        # optional but safe
                worker_pbar.set_postfix_str("Idle")
                worker_pbar.reset(total=0)
                if not is_slow:
                    WORKER_STATUS[worker_id].update(
                        {
                            "status": "idle",
                            "task": None,
                            "started_at": None,
                            "preferred_model": None,
                            "last_completed": idea.get('title', 'Unknown'),
                        }
                    )
                    update_status_file()
                # Mark task as done in both queues (safe to call even if not from that queue)
                try:
                    JOB_QUEUE.task_done()
                except ValueError:
                    pass
                try:
                    SLOW_QUEUE.task_done()
                except ValueError:
                    pass
        except asyncio.CancelledError:
            # Get the task name before resetting status
            timed_out_task = WORKER_STATUS[worker_id].get("task")
            
            tqdm.write(f"🔄 Worker {worker_id} cancelled due to timeout, restarting...")
            
            # CRITICAL: Prune the timed-out idea so retry_manager can add new ones
            if timed_out_task:
                await prune_idea_from_log(timed_out_task)
                tqdm.write(f"🧹 Pruned timed-out task '{timed_out_task}' from queue")
            
            # Reset worker status and continue loop (will restart automatically)
            WORKER_STATUS[worker_id].update({
                "status": "idle",
                "task": None,
                "started_at": None,
                "preferred_model": None,
            })
            update_status_file()
            await asyncio.sleep(1)  # Brief pause before restarting
            continue

# -------------------- RAM-aware task loader --------------------
async def enqueue_tasks(ideas):
    """
    Enqueue tasks from initial list and wait if RAM usage is high.
    """
    for idea in ideas:
        # Optional RAM throttling
        while psutil.Process().memory_info().rss / 1024**2 > RAM_THRESHOLD_MB:
            tqdm.write("⚠️ RAM usage high, waiting before adding more tasks...")
            await asyncio.sleep(CHECK_RAM_INTERVAL)
        prio = 0 if PREFERRED_MODEL == "deepseek-r1" else 5
        await enqueue_task(idea, priority=prio)


def load_ideas_from_log():
    """Load ideas from ideas_log.json if present."""
    if not IDEAS_LOG_PATH.exists():
        return []
    try:
        ideas = _read_json_locked(IDEAS_LOG_PATH, [])
        return ideas if isinstance(ideas, list) else []
    except Exception as e:
        tqdm.write(f"⚠️ Failed to load ideas_log.json: {e}")
        return []


def load_qa_issues_from_log():
    """Load QA issues from QAissue.json if present."""
    if not QA_ISSUE_PATH.exists():
        return []
    try:
        issues = _read_json_locked(QA_ISSUE_PATH, [])
        return issues if isinstance(issues, list) else []
    except Exception as e:
        tqdm.write(f"⚠️ Failed to load QAissue.json: {e}")
        return []

# -------------------- Main Async Entry --------------------
async def run_workers():
    # Ensure input/output directories exist
    Path(IMPLEMENTATIONS_DIR).mkdir(exist_ok=True)
    Path(OUTPUT_PROJECT_DIR).mkdir(exist_ok=True)

    # Load existing JSON tasks
    ideas = []
    for filename in os.listdir(IMPLEMENTATIONS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(IMPLEMENTATIONS_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        ideas.extend(data)
                    else:
                        ideas.append(data)
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            except Exception as e:
                tqdm.write(f"❌ Failed to load {filename}: {e}")

    # Load tasks from ideas_log.json
    ideas_from_log = load_ideas_from_log()
    if ideas_from_log:
        ideas.extend(ideas_from_log)
        tqdm.write(f"ℹ️ Loaded {len(ideas_from_log)} tasks from ideas_log.json")
    global IDEAS_LOG_LAST_SIZE, IDEAS_LOG_LAST_MTIME
    IDEAS_LOG_LAST_SIZE = len(ideas_from_log)  # Track count of processed ideas
    if IDEAS_LOG_PATH.exists():
        IDEAS_LOG_LAST_MTIME = IDEAS_LOG_PATH.stat().st_mtime  # Track mtime for polling

    # Load tasks from QAissue.json (retry_manager dedicated queue)
    qa_issues_from_log = load_qa_issues_from_log()
    if qa_issues_from_log:
        ideas.extend(qa_issues_from_log)
        tqdm.write(f"ℹ️ Loaded {len(qa_issues_from_log)} tasks from QAissue.json")
    global QA_ISSUE_LAST_SIZE, QA_ISSUE_LAST_MTIME
    QA_ISSUE_LAST_SIZE = len(qa_issues_from_log)  # Track count of processed items
    if QA_ISSUE_PATH.exists():
        QA_ISSUE_LAST_MTIME = QA_ISSUE_PATH.stat().st_mtime  # Track mtime for polling

    if not ideas:
        tqdm.write("⚠️ No tasks found initially.")

    # Main overall progress bar
    main_pbar = tqdm(
        total=len(ideas),
        position=0,
        desc="Overall Progress",
        bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
    )

    # Spawn workers and track them for timeout management
    global WORKER_TASKS
    workers = []
    for i in range(NUM_WORKERS):
        task = asyncio.create_task(worker(i, main_pbar))
        workers.append(task)
        WORKER_TASKS[i] = task

    # Start model health monitor
    monitor_task = asyncio.create_task(monitor_models())
    
    # Start worker timeout monitor
    timeout_monitor = asyncio.create_task(monitor_worker_timeouts())
    
    # Start periodic status updater (keeps monitor fresh)
    status_updater = asyncio.create_task(update_status_periodically())

    # Enqueue initial tasks
    await enqueue_tasks(ideas)

    # Start polling tasks instead of file watchers (prevents deadlock race conditions)
    polling_tasks = [
        asyncio.create_task(poll_implementations_dir()),
        asyncio.create_task(poll_ideas_log_changes()),
        asyncio.create_task(poll_qa_issues_changes()),
        asyncio.create_task(forced_periodic_reload()),  # Force reload every 5 min (catches mtime misses)
        asyncio.create_task(detect_stuck_workers()),    # Detect and recover from stuck idle state
    ]

    try:
        while True:
            await asyncio.sleep(1)
            # adjust main bar total for both queues
            main_pbar.total = main_pbar.n + JOB_QUEUE.qsize() + SLOW_QUEUE.qsize()
            main_pbar.refresh()
    except KeyboardInterrupt:
        tqdm.write("🛑 Shutting down...")
    finally:
        # Cancel all polling tasks
        for task in polling_tasks:
            task.cancel()
        # Cancel worker tasks
        for w in workers:
            w.cancel()
        # Cancel monitor tasks
        monitor_task.cancel()
        timeout_monitor.cancel()
        status_updater.cancel()
        # Wait for all to finish
        await asyncio.gather(*polling_tasks, *workers, monitor_task, timeout_monitor, status_updater, return_exceptions=True)
        main_pbar.close()


if __name__ == "__main__":
    asyncio.run(run_workers())
