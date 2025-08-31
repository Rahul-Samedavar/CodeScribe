"""This module provides the `ReadmeGenerator` class, which is responsible for generating README.md files for a given project directory.  It uses an LLM to create comprehensive README files for the project root and subdirectories based on code analysis and user-provided descriptions.  The module handles file parsing, prompt generation, LLM interaction, and progress reporting, ensuring efficient and accurate README generation."""
import os
import shutil
import ast
from pathlib import Path
from typing import List, Callable
from . import scanner
from .llm_handler import LLMHandler
SUBDIR_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert technical writer creating a README.md file for a specific directory within a larger project. Your tone should be informative and concise.\n\nUSER:\nYou are generating a `README.md` for the directory: `{current_dir_relative}`\n\nThe overall project description is:\n"{project_description}"\n\n---\nThis directory contains the following source code files. Use them to describe the specific purpose of this directory:\n{file_summaries}\n---\n\nThis directory also contains the following subdirectories. Use their `README.md` content (provided below) to summarize their roles:\n{subdirectory_readmes}\n---\n\nTASK:\nWrite a `README.md` for the `{current_dir_relative}` directory.\n- Start with a heading (e.g., `# Directory: {dir_name}`).\n- Briefly explain the purpose of this directory based on the files it contains.\n- If there are subdirectories, provide a section summarizing what each one does, using the context from their READMEs.\n- Use clear Markdown formatting. Do not describe the entire project; focus ONLY on the contents and role of THIS directory.\n'
ROOT_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert technical writer creating the main `README.md` for an entire software project. Your tone should be welcoming and comprehensive.\n\nUSER:\nYou are generating the main `README.md` for a project.\n\nThe user-provided project description is:\n"{project_description}"\n\n---\nThe project\'s root directory contains the following source code files:\n{file_summaries}\n---\n\nThe project has the following main subdirectories. Use their `README.md` content (provided below) to describe the overall structure of the project:\n{subdirectory_readmes}\n---\n\nTASK:\nWrite a comprehensive `README.md` for the entire project. Structure it with the following sections:\n- A main title (`# Project: {project_name}`).\n- **Overview**: A slightly more detailed version of the user\'s description, enhanced with context from the files and subdirectories.\n- **Project Structure**: A description of the key directories and their roles, using the information from the subdirectory READMEs.\n- **Key Features**: Infer and list the key features of the project based on all the provided context.\n'
UPDATE_SUBDIR_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert technical writer updating a README.md file for a specific directory. Your tone should be informative and concise. A user has provided a note with instructions.\n\nUSER:\nYou are updating the `README.md` for the directory: `{current_dir_relative}`\n\nThe user-provided note with instructions for this update is:\n"{user_note}"\n\nThe overall project description is:\n"{project_description}"\n---\nThis directory contains the following source code files. Use them to describe the specific purpose of this directory:\n{file_summaries}\n---\nThis directory also contains the following subdirectories. Use their `README.md` content (provided below) to summarize their roles:\n{subdirectory_readmes}\n---\nHere is the OLD `README.md` content. You must update it based on the new context and the user\'s note.\n---\n{existing_readme}\n---\nTASK:\nRewrite the `README.md` for the `{current_dir_relative}` directory, incorporating the user\'s note and any new information from the files and subdirectories.\n- Start with a heading (e.g., `# Directory: {dir_name}`).\n- Use the existing content as a base, but modify it as needed.\n- Use clear Markdown formatting. Do not describe the entire project; focus ONLY on the contents and role of THIS directory.\n'
UPDATE_ROOT_PROMPT_TEMPLATE = '\nSYSTEM: You are an expert technical writer updating the main `README.md` for an entire software project. Your tone should be welcoming and comprehensive. A user has provided a note with instructions.\n\nUSER:\nYou are updating the main `README.md` for a project.\n\nThe user-provided note with instructions for this update is:\n"{user_note}"\n\nThe user-provided project description is:\n"{project_description}"\n---\nThe project\'s root directory contains the following source code files:\n{file_summaries}\n---\nThe project has the following main subdirectories. Use their `README.md` content (provided below) to describe the overall structure of the project:\n{subdirectory_readmes}\n---\nHere is the OLD `README.md` content. You must update it based on the new context and the user\'s note.\n---\n{existing_readme}\n---\nTASK:\nRewrite a comprehensive `README.md` for the entire project. Structure it with the following sections, using the old README as a base but incorporating changes based on the user\'s note and new context.\n- A main title (`# Project: {project_name}`).\n- **Overview**: An updated version of the user\'s description, enhanced with context.\n- **Project Structure**: A description of the key directories and their roles.\n- **Key Features**: Infer and list key features based on all the provided context.\n'

def no_op_callback(event: str, data: dict):
    pass

class ReadmeGenerator:

    def __init__(self, path_or_url: str, description: str, exclude: List[str], llm_handler: LLMHandler, user_note: str='', repo_full_name='', progress_callback: Callable[[str, dict], None]=no_op_callback):
        """Initializes a new instance of the `ReadmeGenerator` class.

:param path_or_url: The path to the project directory or a URL to a Git repository.
:type path_or_url: str
:param description: A brief description of the project.
:type description: str
:param exclude: A list of files or directories to exclude from processing.
:type exclude: List[str]
:param llm_handler: An instance of the LLMHandler class for interacting with the large language model.
:type llm_handler: LLMHandler
:param user_note: A user-provided note with instructions for updating READMEs (optional).
:type user_note: str
:param repo_full_name: The full name of the GitHub repository (e.g., 'username/repository') (optional).
:type repo_full_name: str
:param progress_callback: A callback function to report progress updates (optional).
:type progress_callback: Callable[[str, dict], None]"""
        self.path_or_url = path_or_url
        self.description = description
        self.exclude = exclude + ['README.md']
        self.llm_handler = llm_handler
        self.user_note = user_note
        self.progress_callback = progress_callback
        self.project_path = None
        self.is_temp_dir = path_or_url.startswith('http')
        self.repo_full_name = repo_full_name

        def llm_log_wrapper(message: str):
            self.progress_callback('log', {'message': message})
        self.llm_handler.progress_callback = llm_log_wrapper

    def run(self):
        """Public method to start README generation. This method handles potential exceptions and cleanup of temporary directories."""
        try:
            self.project_path = scanner.get_project_path(self.path_or_url)
            self.progress_callback('phase', {'id': 'readmes', 'name': 'Generating READMEs', 'status': 'in-progress'})
            self.run_with_structured_logging()
            self.progress_callback('phase', {'id': 'readmes', 'status': 'success'})
        except Exception as e:
            self.progress_callback('log', {'message': f'An unexpected error occurred in README generation: {e}'})
            self.progress_callback('phase', {'id': 'readmes', 'status': 'error'})
            raise
        finally:
            if self.is_temp_dir and self.project_path and self.project_path.exists():
                shutil.rmtree(self.project_path, ignore_errors=True)

    def _summarize_py_file(self, file_path: Path) -> str:
        """Extracts the module-level docstring, or a list of function/class names as a fallback, to summarize a Python file.

:param file_path: The path to the Python file.
:type file_path: Path
:return: A summary of the Python file's contents.
:rtype: str"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)
            if docstring:
                return f'`{file_path.name}`: {docstring.strip().splitlines()[0]}'
            definitions = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    definitions.append(node.name)
            if definitions:
                summary = f"Contains definitions for: `{', '.join(definitions)}`."
                return f'`{file_path.name}`: {summary}'
        except Exception as e:
            self.progress_callback('log', {'message': f'Could not parse {file_path.name} for summary: {e}'})
        return f'`{file_path.name}`: A Python source file.'

    def run_with_structured_logging(self):
        """Generates README files for each directory from the bottom up, emitting structured events for the UI."""
        if not self.project_path:
            self.project_path = scanner.get_project_path(self.path_or_url)
        for dir_path, subdir_names, file_names in os.walk(self.project_path, topdown=False):
            current_dir = Path(dir_path)
            if scanner.is_excluded(current_dir, self.exclude, self.project_path):
                continue
            rel_path = current_dir.relative_to(self.project_path).as_posix()
            dir_id = rel_path if rel_path != '.' else 'root'
            dir_name_display = rel_path if rel_path != '.' else 'Project Root'
            self.progress_callback('subtask', {'parentId': 'readmes', 'listId': 'readme-dir-list', 'id': dir_id, 'name': f'Directory: {dir_name_display}', 'status': 'in-progress'})
            try:
                file_summaries = self._gather_file_summaries(current_dir, file_names)
                subdirectory_readmes = self._gather_subdirectory_readmes(current_dir, subdir_names)
                existing_readme_content = None
                existing_readme_path = current_dir / 'README.md'
                if existing_readme_path.exists():
                    with open(existing_readme_path, 'r', encoding='utf-8') as f:
                        existing_readme_content = f.read()
                prompt = self._build_prompt(current_dir, file_summaries, subdirectory_readmes, existing_readme_content)
                generated_content = self.llm_handler.generate_text_response(prompt)
                with open(current_dir / 'README.md', 'w', encoding='utf-8') as f:
                    f.write(generated_content)
                self.progress_callback('subtask', {'parentId': 'readmes', 'id': dir_id, 'status': 'success'})
            except Exception as e:
                self.progress_callback('log', {'message': f'Failed to generate README for {dir_name_display}: {e}'})
                self.progress_callback('subtask', {'parentId': 'readmes', 'id': dir_id, 'status': 'error'})

    def _gather_file_summaries(self, current_dir: Path, file_names: List[str]) -> str:
        """Gathers summaries for Python files within a directory.

:param current_dir: The path to the current directory.
:type current_dir: Path
:param file_names: A list of file names in the current directory.
:type file_names: List[str]
:return: A string containing summaries of the Python files.
:rtype: str"""
        file_summaries_list = []
        for fname in file_names:
            if fname.endswith('.py'):
                file_path = current_dir / fname
                if not scanner.is_excluded(file_path, self.exclude, self.project_path):
                    file_summaries_list.append(self._summarize_py_file(file_path))
        return '\n'.join(file_summaries_list) or 'No Python source files in this directory.'

    def _gather_subdirectory_readmes(self, current_dir: Path, subdir_names: List[str]) -> str:
        """Gathers README content from subdirectories.

:param current_dir: The path to the current directory.
:type current_dir: Path
:param subdir_names: A list of subdirectory names.
:type subdir_names: List[str]
:return: A string containing README content from subdirectories.
:rtype: str"""
        subdir_readmes_list = []
        for sub_name in subdir_names:
            readme_path = current_dir / sub_name / 'README.md'
            if readme_path.exists():
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                subdir_readmes_list.append(f'--- Subdirectory: `{sub_name}` ---\n{content}\n')
        return '\n'.join(subdir_readmes_list) or 'No subdirectories with READMEs.'

    def _build_prompt(self, current_dir: Path, file_summaries: str, subdirectory_readmes: str, existing_readme: str | None) -> str:
        """Constructs the prompt for the LLM based on the current directory, files, subdirectories, and existing README content.

:param current_dir: The path to the current directory.
:type current_dir: Path
:param file_summaries: Summaries of files in the current directory.
:type file_summaries: str
:param subdirectory_readmes: README content from subdirectories.
:type subdirectory_readmes: str
:param existing_readme: The content of an existing README file (optional).
:type existing_readme: str | None
:return: The prompt for the LLM.
:rtype: str"""
        is_root = current_dir == self.project_path
        common_args = {'project_description': self.description, 'file_summaries': file_summaries, 'subdirectory_readmes': subdirectory_readmes, 'user_note': self.user_note or 'No specific instructions provided.'}
        if is_root:
            template = UPDATE_ROOT_PROMPT_TEMPLATE if existing_readme else ROOT_PROMPT_TEMPLATE
            args = {**common_args, 'project_name': self.repo_full_name if self.repo_full_name else self.project_path.name}
            if existing_readme:
                args['existing_readme'] = existing_readme
        else:
            template = UPDATE_SUBDIR_PROMPT_TEMPLATE if existing_readme else SUBDIR_PROMPT_TEMPLATE
            args = {**common_args, 'current_dir_relative': current_dir.relative_to(self.project_path).as_posix(), 'dir_name': current_dir.name}
            if existing_readme:
                args['existing_readme'] = existing_readme
        return template.format(**args)