"""This module orchestrates the process of generating AI-powered documentation for Python projects. It handles project scanning, dependency analysis, docstring generation using an LLM, and updating source files.  It supports processing projects from local paths or URLs and optionally pushes changes to a GitHub repository."""
import shutil
from pathlib import Path
from typing import List, Callable, Dict
import networkx as nx
import json
from collections import defaultdict
from . import scanner, parser, updater
from .llm_handler import LLMHandler
COMBINED_DOCSTRING_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert programmer writing high-quality, comprehensive Python docstrings in reStructuredText (reST) format. Your output MUST be a single JSON object.\n\nUSER:\nProject Description:\n"""\n{project_description}\n"""\n\n---\nCONTEXT FROM DEPENDENCIES:\nThis file depends on other modules. Here is their documentation for context:\n\n{dependency_context}\n---\n\nDOCUMENT THE FOLLOWING SOURCE FILE:\n\nFile Path: `{file_path}`\n\n```python\n{file_content}\n```\nINSTRUCTIONS:\nProvide a single JSON object as your response.\n1.  The JSON object MUST have a special key `"__module__"`. The value for this key should be a concise, single-paragraph docstring that summarizes the purpose of the entire file.\n2.  The other keys in the JSON object should be the function or class names (e.g., "my_function", "MyClass", "MyClass.my_method").\n3.  The values for these other keys should be their complete docstrings.\n4.  Do NOT include the original code in your response. Only generate the JSON containing the docstrings.\n'
PACKAGE_INIT_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert programmer writing a high-level, one-paragraph summary for a Python package. This summary will be the main docstring for the package\'s `__init__.py` file.\n\nUSER:\nProject Description:\n"""\n{project_description}\n"""\n\nYou are writing the docstring for the `__init__.py` of the `{package_name}` package.\n\nThis package contains the following modules. Their summaries are provided below:\n{module_summaries}\n\nINSTRUCTIONS:\nWrite a concise, single-paragraph docstring that summarizes the overall purpose and responsibility of the `{package_name}` package, based on the modules it contains. This docstring will be placed in the `__init__.py` file.\n'

def no_op_callback(event: str, data: dict):
    print(f'{event}: {json.dumps(data, indent=2)}')

class DocstringOrchestrator:

    def __init__(self, path_or_url: str, description: str, exclude: List[str], llm_handler: LLMHandler, progress_callback: Callable[[str, dict], None]=no_op_callback, repo_full_name: str=None):
        """Initializes a new instance of the `DocstringOrchestrator` class.

:param path_or_url: The path to the project directory or a URL to a Git repository.
:type path_or_url: str
:param description: A brief description of the project.
:type description: str
:param exclude: A list of files or directories to exclude from processing.
:type exclude: List[str]
:param llm_handler: An instance of the LLMHandler class for interacting with the large language model.
:type llm_handler: LLMHandler
:param progress_callback: A callback function to report progress updates. Defaults to a simple print function.
:type progress_callback: Callable[[str, dict], None]
:param repo_full_name: The full name of the GitHub repository (e.g., 'username/repository').  Used for root package name when generating the init docstring.
:type repo_full_name: str, optional"""
        self.path_or_url = path_or_url
        self.description = description
        self.exclude = exclude
        self.llm_handler = llm_handler
        self.progress_callback = progress_callback
        self.project_path = None
        self.is_temp_dir = path_or_url.startswith('http')
        self.repo_full_name = repo_full_name

        def llm_log_wrapper(message: str):
            self.progress_callback('log', {'message': message})
        self.llm_handler.progress_callback = llm_log_wrapper

    def run(self):
        """Runs the documentation generation process. This includes scanning the project, building a dependency graph, generating docstrings using an LLM, updating the source files, and optionally cleaning up temporary directories.

The process is divided into phases: scanning, docstring generation and packaging docstring generation.  Progress is reported via the provided progress_callback.

:raises Exception: If any errors occur during the process."""

        def log_to_ui(message: str):
            self.progress_callback('log', {'message': message})
        try:
            self.project_path = scanner.get_project_path(self.path_or_url, log_callback=log_to_ui)
            self.progress_callback('phase', {'id': 'scan', 'name': 'Scanning Project', 'status': 'in-progress'})
            files = scanner.scan_project(self.project_path, self.exclude)
            log_to_ui(f'Found {len(files)} Python files to document.')
            self.progress_callback('phase', {'id': 'scan', 'status': 'success'})
            graph = parser.build_dependency_graph(files, self.project_path, log_callback=log_to_ui)
            self.progress_callback('phase', {'id': 'docstrings', 'name': 'Generating Docstrings', 'status': 'in-progress'})
            doc_order = list(nx.topological_sort(graph)) if nx.is_directed_acyclic_graph(graph) else list(graph.nodes)
            documented_context = {}
            module_docstrings = {}
            for file_path in doc_order:
                rel_path = file_path.relative_to(self.project_path).as_posix()
                self.progress_callback('subtask', {'parentId': 'docstrings', 'listId': 'docstring-file-list', 'id': f'doc-{rel_path}', 'name': f'Documenting {rel_path}', 'status': 'in-progress'})
                deps = graph.predecessors(file_path)
                dep_context_str = '\n'.join([f'File: `{dep.relative_to(self.project_path)}`\n{json.dumps(documented_context.get(dep, {}), indent=2)}\n' for dep in deps]) or 'No internal dependencies have been documented yet.'
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                prompt = COMBINED_DOCSTRING_PROMPT_TEMPLATE.format(project_description=self.description, dependency_context=dep_context_str, file_path=rel_path, file_content=file_content)
                try:
                    combined_docs = self.llm_handler.generate_documentation(prompt)
                    module_summary = combined_docs.pop('__module__', None)
                    function_class_docs = combined_docs
                    updater.update_file_with_docstrings(file_path, function_class_docs, log_callback=log_to_ui)
                    if module_summary:
                        updater.update_module_docstring(file_path, module_summary, log_callback=log_to_ui)
                        module_docstrings[file_path] = module_summary
                    self.progress_callback('subtask', {'parentId': 'docstrings', 'id': f'doc-{rel_path}', 'status': 'success'})
                    documented_context[file_path] = function_class_docs
                except Exception as e:
                    log_to_ui(f'Error processing docstrings for {rel_path}: {e}')
                    self.progress_callback('subtask', {'parentId': 'docstrings', 'id': f'doc-{rel_path}', 'status': 'error'})
            packages = defaultdict(list)
            for file_path, docstring in module_docstrings.items():
                if file_path.name != '__init__.py':
                    packages[file_path.parent].append(f'- `{file_path.name}`: {docstring}')
            for package_path, summaries in packages.items():
                rel_path = package_path.relative_to(self.project_path).as_posix()
                init_file = package_path / '__init__.py'
                self.progress_callback('subtask', {'parentId': 'docstrings', 'listId': 'docstring-package-list', 'id': f'pkg-{rel_path}', 'name': f'Package summary for {rel_path}', 'status': 'in-progress'})
                try:
                    is_root_package = package_path == self.project_path
                    package_name = self.repo_full_name if is_root_package and self.repo_full_name else package_path.name
                    prompt = PACKAGE_INIT_PROMPT_TEMPLATE.format(project_description=self.description, package_name=package_name, module_summaries='\n'.join(summaries))
                    package_summary = self.llm_handler.generate_text_response(prompt).strip().strip('"""').strip("'''").strip()
                    if not init_file.exists():
                        init_file.touch()
                    updater.update_module_docstring(init_file, package_summary, log_callback=log_to_ui)
                    self.progress_callback('subtask', {'parentId': 'docstrings', 'id': f'pkg-{rel_path}', 'status': 'success'})
                except Exception as e:
                    log_to_ui(f'Error generating package docstring for {rel_path}: {e}')
                    self.progress_callback('subtask', {'parentId': 'docstrings', 'id': f'pkg-{rel_path}', 'status': 'error'})
            self.progress_callback('phase', {'id': 'docstrings', 'status': 'success'})
        finally:
            if self.is_temp_dir and self.project_path and self.project_path.exists():
                shutil.rmtree(self.project_path, ignore_errors=True)