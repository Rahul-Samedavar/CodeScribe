# codescribe/orchestrator.py

import shutil
from pathlib import Path
from typing import List, Callable, Dict
import networkx as nx
import json

from . import scanner, parser, updater
from .llm_handler import LLMHandler

PROMPT_TEMPLATE = """
SYSTEM: You are an expert programmer writing high-quality, comprehensive Python docstrings in reStructuredText (reST) format. Analyze the provided code and generate docstrings for each function and class.

USER:
Project Description:
\"\"\"
{project_description}
\"\"\"

---
CONTEXT FROM DEPENDENCIES:
This file depends on other modules. Here is their documentation for context:

{dependency_context}
---

DOCUMENT THE FOLLOWING SOURCE FILE:

File Path: `{file_path}`

```python
{file_content}
INSTRUCTIONS:
Provide a JSON object where keys are the function or class names (e.g., "my_function", "MyClass", "MyClass.my_method") and values are their complete docstrings. Do NOT include the code itself in your response.
"""


# Helper no-op function for default callback
def no_op_callback(event: str, data: dict):
    print(f"{event}: {json.dumps(data, indent=2)}")

class DocstringOrchestrator:
    # Add 'progress_callback' to __init__
    def __init__(self, path_or_url: str, description: str, exclude: List[str], llm_handler: LLMHandler, progress_callback: Callable[[str, dict], None] = no_op_callback):
        self.path_or_url = path_or_url
        self.description = description
        self.exclude = exclude
        self.llm_handler = llm_handler
        self.progress_callback = progress_callback
        self.project_path = None
        self.is_temp_dir = path_or_url.startswith("http")
        
        # --- NEW: Bridge the LLM Handler's simple log callback to our structured event callback ---
        # This ensures messages like "Rate limit hit..." are sent to the frontend.
        def llm_log_wrapper(message: str):
            self.progress_callback("log", {"message": message})
        
        self.llm_handler.progress_callback = llm_log_wrapper
        # --- END NEW ---

    def run(self):
        try:
            # Use the callback instead of print()]
            self.project_path = scanner.get_project_path(self.path_or_url)
            
            
            self.progress_callback("phase", {"id": "scan", "name": "Scanning Project", "status": "in-progress"})
            files = scanner.scan_project(self.project_path, self.exclude)
            self.progress_callback("log", {"message": f"Found {len(files)} Python files to document."})
            self.progress_callback("phase", {"id": "scan", "status": "success"})

            graph = parser.build_dependency_graph(files, self.project_path)
            
            
            self.progress_callback("phase", {"id": "docstrings", "name": "Generating Docstrings", "status": "in-progress"})
            if not nx.is_directed_acyclic_graph(graph):
                doc_order = list(graph.nodes)
            else:
                doc_order = list(nx.topological_sort(graph))
            
            documented_context = {}
            for file_path in doc_order:
                
                rel_path = file_path.relative_to(self.project_path).as_posix()
                # MODIFIED: Added 'listId' to the subtask payload.
                self.progress_callback("subtask", {
                    "parentId": "docstrings", 
                    "listId": "docstring-file-list", # This tells the JS where to put the item
                    "id": rel_path, 
                    "name": rel_path, 
                    "status": "in-progress"
                })
                
                deps = graph.predecessors(file_path)
                dep_context_str = ""
                for dep in deps:
                    if dep in documented_context:
                        dep_context_str += f"File: `{dep.relative_to(self.project_path)}`\n"
                        dep_context_str += json.dumps(documented_context[dep], indent=2)
                        dep_context_str += "\n\n"
                
                if not dep_context_str:
                    dep_context_str = "No internal dependencies have been documented yet."
                    
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                
                prompt = PROMPT_TEMPLATE.format(
                    project_description=self.description,
                    dependency_context=dep_context_str,
                    file_path=file_path.relative_to(self.project_path),
                    file_content=file_content
                )
                
                try:
                    generated_docs = self.llm_handler.generate_documentation(prompt)
                    
                    updater.update_file_with_docstrings(file_path, generated_docs)
                    
                    # MODIFIED: Added 'listId' here as well for consistency.
                    self.progress_callback("subtask", {
                        "parentId": "docstrings", 
                        "listId": "docstring-file-list",
                        "id": rel_path, 
                        "status": "success"
                    })
                    documented_context[file_path] = generated_docs
                    
                except Exception as e:
                    self.progress_callback("log", {"message": f"Error on {rel_path}: {e}"})
                    # MODIFIED: Added 'listId' here for error state.
                    self.progress_callback("subtask", {
                        "parentId": "docstrings",
                        "listId": "docstring-file-list",
                        "id": rel_path, 
                        "status": "error"
                    })
                    continue

            self.progress_callback("phase", {"id": "docstrings", "status": "success"})

        finally:
            if self.is_temp_dir and self.project_path and self.project_path.exists():
                shutil.rmtree(self.project_path, ignore_errors=True)