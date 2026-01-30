import asyncio
import json
import os
from tqdm import tqdm
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

NUM_WORKERS = 4
JOB_QUEUE = asyncio.Queue()
IMPLEMENTATIONS_DIR = "./implementations"

# --- Example CodeImplementer with progress support ---
class CodeImplementer:
    """Simulate long-running task with progress reporting"""
    def __init__(self, idea):
        self.idea = idea
        self.total_steps = idea.get("steps", 10)  # default 10 steps

    async def implement_async(self, progress_callback=None):
        for step in range(1, self.total_steps + 1):
            await asyncio.sleep(0.2)  # simulate work
            if progress_callback:
                progress_callback(1)  # increment progress by 1 step

# --- File watcher ---
class ImplementationHandler(FileSystemEventHandler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".json"):
            asyncio.get_event_loop().create_task(self.load_file(event.src_path))

    async def load_file(self, path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for task in data:
                        await self.queue.put(task)
                else:
                    await self.queue.put(data)
            tqdm.write(f"✅ Loaded tasks from {os.path.basename(path)}")
        except Exception as e:
            tqdm.write(f"❌ Failed to load {os.path.basename(path)}: {e}")

# --- Worker ---
async def worker(worker_id, main_pbar):
    # Enhanced bar format with percentage, ETA, and task name
    worker_pbar = tqdm(
        total=0,
        position=worker_id + 1,
        desc=f"Worker {worker_id}",
        leave=False,
        bar_format="{desc} |{bar}| {percentage:3.0f}% [{elapsed}<{remaining}] {postfix}"
    )

    while True:
        idea = await JOB_QUEUE.get()
        steps = idea.get("steps", 10)
        worker_pbar.reset(total=steps)
        worker_pbar.set_postfix_str(f"{idea.get('name', 'Task')}")

        def progress_callback(n):
            worker_pbar.update(n)

        try:
            impl = CodeImplementer(idea)
            await impl.implement_async(progress_callback)
        except Exception as e:
            tqdm.write(f"✗ Worker {worker_id} error: {e}")
        finally:
            main_pbar.update(1)
            worker_pbar.set_postfix_str("Idle")
            worker_pbar.reset(total=0)  # clear bar for next task
            JOB_QUEUE.task_done()

# --- Main async entry ---
async def run_workers():
    # Load existing JSONs in folder
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
            except Exception as e:
                tqdm.write(f"❌ Failed to load {filename}: {e}")

    if not ideas:
        tqdm.write("⚠️ No tasks found in ./implementations initially.")

    # Main overall progress bar
    main_pbar = tqdm(
        total=len(ideas),
        position=0,
        desc="Overall Progress",
        bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
    )

    # Spawn workers
    workers = [asyncio.create_task(worker(i, main_pbar)) for i in range(NUM_WORKERS)]

    # Push initial ideas to queue
    for idea in ideas:
        await JOB_QUEUE.put(idea)

    # Setup file watcher for dynamic tasks
    event_handler = ImplementationHandler(JOB_QUEUE)
    observer = Observer()
    observer.schedule(event_handler, IMPLEMENTATIONS_DIR, recursive=False)
    observer.start()

    try:
        while True:
            await asyncio.sleep(1)
            # Adjust main bar total for any new tasks
            main_pbar.total = main_pbar.n + JOB_QUEUE.qsize()
            main_pbar.refresh()
    except KeyboardInterrupt:
        tqdm.write("🛑 Shutting down...")
    finally:
        observer.stop()
        observer.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        main_pbar.close()
