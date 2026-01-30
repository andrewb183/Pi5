#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import time
import json
import os
import requests
import random
import subprocess
from datetime import datetime

class IdeaGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Background Code Idea Generator")
        self.root.geometry("600x500")
        
        self.models = ["qwen2.5-coder", "llama2", "deepseek-r1"]
        self.languages = ["Python", "JavaScript", "Java", "C++", "C#", "Go", "Rust"]
        self.idea_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.mode = "Generate"
        self.loaded_ideas = []
        self.web_ideas_used = []
        
        # GUI Elements
        frame = ttk.Frame(root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Mode selection
        ttk.Label(frame, text="Mode:").grid(row=0, column=0, sticky=tk.W)
        self.mode_var = tk.StringVar(value="Generate")
        ttk.Radiobutton(frame, text="Generate New Ideas", variable=self.mode_var, 
                        value="Generate", command=self.update_mode).grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(frame, text="Load Ideas from File", variable=self.mode_var, 
                        value="Load", command=self.update_mode).grid(row=0, column=2, sticky=tk.W)
        ttk.Radiobutton(frame, text="Fetch Ideas from Web", variable=self.mode_var, 
                        value="Web", command=self.update_mode).grid(row=0, column=3, sticky=tk.W)
        
        # Load button
        self.load_button = ttk.Button(frame, text="Select Ideas File", 
                                      command=self.load_ideas_from_file, state=tk.DISABLED)
        self.load_button.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.EW)
        
        # Start/Stop button
        self.start_stop_button = ttk.Button(frame, text="Start Generation", 
                                           command=self.toggle_generation)
        self.start_stop_button.grid(row=1, column=2, columnspan=2, pady=5, sticky=tk.EW)
        
        # Status label
        self.status_label = ttk.Label(frame, text="Status: Stopped")
        self.status_label.grid(row=2, column=0, columnspan=4, pady=5, sticky=tk.W)
        
        # Log display
        ttk.Label(frame, text="Generation Log:").grid(row=3, column=0, columnspan=4, sticky=tk.W)
        self.log_text = scrolledtext.ScrolledText(frame, height=15, width=70)
        self.log_text.grid(row=4, column=0, columnspan=4, sticky=tk.NSEW, pady=5)
        
        frame.grid_rowconfigure(4, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # Load existing ideas log
        self.load_ideas_log()
        
        # Start popup checker
        self.check_popup_queue()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def update_mode(self):
        self.mode = self.mode_var.get()
        if self.mode == "Load":
            self.load_button.config(state=tk.NORMAL)
        else:
            self.load_button.config(state=tk.DISABLED)
    
    def toggle_generation(self):
        if self.running:
            self.running = False
            self.status_label.config(text="Status: Stopping...")
            if self.thread:
                self.thread.join(timeout=2)
            self.start_stop_button.config(text="Start Generation")
            self.log("Generation stopped")
            self.status_label.config(text="Status: Stopped")
        else:
            self.running = True
            self.thread = threading.Thread(target=self.generation_loop, daemon=True)
            self.thread.start()
            self.start_stop_button.config(text="Stop Generation")
            self.log("Generation started")
            self.status_label.config(text="Status: Running")
    
    def generation_loop(self):
        while self.running:
            try:
                if self.mode == "Load":
                    if self.loaded_ideas:
                        idea = self.loaded_ideas.pop(0)
                        self.idea_queue.put(idea)
                        self.save_idea(idea)
                        self.log(f"Loaded idea: {idea['title']}")
                    else:
                        self.running = False
                        self.root.after(0, lambda: self.status_label.config(text="Status: No more ideas"))
                        break
                elif self.mode == "Web":
                    idea = self.fetch_web_idea()
                    if idea:
                        self.idea_queue.put(idea)
                        self.save_idea(idea)
                        self.log(f"Fetched idea from web: {idea['title']}")
                        # Check if we have a web idea to pass to mk14
                        self.attempt_mk14_integration(idea)
                else:
                    idea = self.generate_idea()
                    if idea:
                        self.idea_queue.put(idea)
                        self.save_idea(idea)
                        self.log(f"Generated idea: {idea['title']}")
                
                time.sleep(300)  # 5 minutes between generations
            except Exception as e:
                self.log(f"Error in generation loop: {str(e)}")
                time.sleep(60)
    
    def generate_idea(self):
        language = random.choice(self.languages)
        prompt = f"Generate a creative idea for a new {language} code project. Provide a title, a brief description, and a sample code snippet. Format as: Title: <title>\nDescription: <desc>\nCode:\n```{language.lower()}\n<code>\n```"
        
        for model in self.models:
            try:
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json().get('response', '')
                    if result:
                        idea = self.parse_idea(result, language)
                        if idea:
                            return idea
            except requests.exceptions.Timeout:
                self.log(f"⚠ Timeout for model {model}, trying next")
            except requests.exceptions.ConnectionError:
                self.log(f"⚠ Connection error for model {model}, trying next")
            except Exception as e:
                self.log(f"⚠ Error with model {model}: {str(e)}, trying next")
        
        self.log("✗ Failed to generate idea from all models")
        return None
    
    def fetch_web_idea(self):
        try:
            response = requests.get(
                "https://api.github.com/search/repositories?q=language:python&sort=stars&order=desc&per_page=20",
                timeout=10
            )
            
            if response.status_code == 200:
                repos = response.json().get('items', [])
                if repos:
                    # Get a random repo that hasn't been used
                    available_repos = [r for r in repos if r['id'] not in self.web_ideas_used]
                    if not available_repos:
                        self.web_ideas_used = []
                        available_repos = repos
                    
                    repo = random.choice(available_repos)
                    self.web_ideas_used.append(repo['id'])
                    
                    title = repo['name']
                    description = repo['description'] or "A trending GitHub repository."
                    url = repo['html_url']
                    code = f"# {title}\n# GitHub: {url}\n# Description: {description}\n# Add your implementation here\nprint('Starting {project_name}')\n".replace('{project_name}', title)
                    
                    language = "Python"
                    return {
                        "title": title,
                        "description": description,
                        "code": code,
                        "language": language,
                        "source": "github",
                        "url": url,
                        "timestamp": time.time()
                    }
        except requests.exceptions.Timeout:
            self.log("⚠ Timeout fetching web ideas")
        except Exception as e:
            self.log(f"⚠ Error fetching web idea: {str(e)}")
        
        return None
    
    def parse_idea(self, response, language):
        lines = response.split('\n')
        title = ""
        description = ""
        code = ""
        in_code = False
        backtick_count = 0
        
        for line in lines:
            if line.startswith("Title:"):
                title = line[6:].strip()
            elif line.startswith("Description:"):
                description = line[12:].strip()
            elif line.startswith("Code:"):
                in_code = True
            elif in_code:
                if line.strip().startswith("```"):
                    backtick_count += 1
                    if backtick_count == 2:
                        break
                else:
                    code += line + '\n'
        
        if title and (description or code):
            return {
                "title": title,
                "description": description,
                "code": code.strip(),
                "language": language,
                "timestamp": time.time()
            }
        
        return None
    
    def save_idea(self, idea):
        ideas_file = os.path.join(os.path.dirname(__file__), "ideas_log.json")
        try:
            if os.path.exists(ideas_file) and os.path.getsize(ideas_file) > 0:
                with open(ideas_file, 'r') as f:
                    ideas = json.load(f)
            else:
                ideas = []
            
            ideas.append(idea)
            
            with open(ideas_file, 'w') as f:
                json.dump(ideas, f, indent=4)
        except Exception as e:
            self.log(f"⚠ Error saving idea: {str(e)}")
    
    def load_ideas_log(self):
        ideas_file = os.path.join(os.path.dirname(__file__), "ideas_log.json")
        try:
            if os.path.exists(ideas_file) and os.path.getsize(ideas_file) > 0:
                with open(ideas_file, 'r') as f:
                    ideas = json.load(f)
                self.log(f"Loaded {len(ideas)} ideas from history (showing last 5)")
                for idea in ideas[-5:]:
                    timestamp = datetime.fromtimestamp(idea['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                    self.log(f"  • {idea['title']} ({timestamp})")
            else:
                self.log("No ideas history found (file empty or missing)")
        except Exception as e:
            self.log(f"⚠ Error loading ideas log: {str(e)}")
    
    def check_popup_queue(self):
        try:
            while True:
                idea = self.idea_queue.get_nowait()
                self.show_popup(idea)
        except queue.Empty:
            pass
        
        self.root.after(1000, self.check_popup_queue)
    
    def load_ideas_from_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    self.loaded_ideas = json.load(f)
                    if not isinstance(self.loaded_ideas, list):
                        self.loaded_ideas = [self.loaded_ideas]
                else:
                    content = f.read()
                    blocks = content.split('---')
                    self.loaded_ideas = []
                    for block in blocks:
                        if block.strip():
                            idea = self.parse_idea(block.strip(), "Python")
                            if idea:
                                self.loaded_ideas.append(idea)
            
            for idea in self.loaded_ideas:
                if 'language' not in idea:
                    idea['language'] = 'Python'
            
            self.log(f"✓ Loaded {len(self.loaded_ideas)} ideas from file")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.log(f"✗ Failed to load file: {str(e)}")
    
    def show_popup(self, idea):
        popup = tk.Toplevel(self.root)
        popup.title("New Code Idea!")
        popup.geometry("600x500")
        popup.attributes('-topmost', True)
        
        # Title
        title_label = ttk.Label(popup, text=f"Title: {idea['title']}", 
                               font=("Arial", 12, "bold"))
        title_label.pack(pady=5)
        
        # Language and metadata
        meta_text = f"Language: {idea.get('language', 'Python')}"
        if 'source' in idea:
            meta_text += f" | Source: {idea['source']}"
        meta_label = ttk.Label(popup, text=meta_text, font=("Arial", 10))
        meta_label.pack(pady=2)
        
        # Description
        desc_label = ttk.Label(popup, text=f"Description: {idea['description']}", 
                              wraplength=550, justify=tk.LEFT)
        desc_label.pack(pady=5, padx=10, fill=tk.X)
        
        # Code display
        code_frame = ttk.Frame(popup)
        code_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        ttk.Label(code_frame, text="Sample Code:").pack(anchor=tk.W)
        
        code_text = scrolledtext.ScrolledText(code_frame, height=12, width=70)
        code_text.insert(tk.END, idea['code'])
        code_text.config(state=tk.DISABLED)
        code_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(popup)
        button_frame.pack(pady=10, fill=tk.X, padx=10)
        
        def save_code():
            lang = idea.get('language', 'Python')
            ext_map = {
                "Python": ".py",
                "JavaScript": ".js",
                "Java": ".java",
                "C++": ".cpp",
                "C#": ".cs",
                "Go": ".go",
                "Rust": ".rs"
            }
            ext = ext_map.get(lang, ".txt")
            filename = f"{idea['title'].replace(' ', '_')}{ext}"
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            try:
                with open(filepath, 'w') as f:
                    f.write(idea['code'])
                messagebox.showinfo("Saved", f"Code saved to {filename}")
                self.log(f"✓ Code saved: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")
                self.log(f"✗ Failed to save code: {str(e)}")
            
            popup.destroy()
        
        def pass_to_mk14():
            if self._has_mk14():
                try:
                    self.log(f"→ Passing idea to mk14: {idea['title']}")
                    # mk14 implementation will be added later
                    subprocess.Popen(["python3", "mk14.py", json.dumps(idea)])
                    messagebox.showinfo("Success", "Idea passed to mk14 for implementation")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to pass to mk14: {str(e)}")
                    self.log(f"✗ Failed to pass to mk14: {str(e)}")
            else:
                messagebox.showinfo("Info", "mk14 program not available yet")
            
            popup.destroy()
        
        def dismiss():
            popup.destroy()
        
        ttk.Button(button_frame, text="Save Code", command=save_code).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pass to mk14", command=pass_to_mk14).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Dismiss", command=dismiss).pack(side=tk.RIGHT, padx=5)
        
        # Make it non-modal
        popup.transient(self.root)
        popup.grab_release()
    
    def _has_mk14(self):
        return os.path.exists(os.path.join(os.path.dirname(__file__), "mk14.py"))
    
    def attempt_mk14_integration(self, idea):
        if self._has_mk14() and idea.get('source') == 'github':
            try:
                self.log(f"→ Attempting to pass web idea to mk14: {idea['title']}")
                subprocess.Popen(["python3", "mk14.py", json.dumps(idea)])
            except Exception as e:
                self.log(f"⚠ Could not pass to mk14: {str(e)}")
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.see(tk.END)
        self.log_text.update()
    
    def on_closing(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.root.destroy()

def main():
    root = tk.Tk()
    app = IdeaGeneratorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
