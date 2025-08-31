# codescribe/readme_generator.py

import os
import shutil
import ast
from pathlib import Path
from typing import List, Callable

from . import scanner
from .llm_handler import LLMHandler

# Prompt templates remain unchanged.
SUBDIR_PROMPT_TEMPLATE = """
SYSTEM: You are an expert technical writer creating a README.md file for a specific directory within a larger project. Your tone should be informative and concise.

USER:
You are generating a `README.md` for the directory: `{current_dir_relative}`

The overall project description is:
"{project_description}"

---
This directory contains the following source code files. Use them to describe the specific purpose of this directory:
{file_summaries}
---

This directory also contains the following subdirectories. Use their `README.md` content (provided below) to summarize their roles:
{subdirectory_readmes}
---

TASK:
Write a `README.md` for the `{current_dir_relative}` directory.
- Start with a heading (e.g., `# Directory: {dir_name}`).
- Briefly explain the purpose of this directory based on the files it contains.
- If there are subdirectories, provide a section summarizing what each one does, using the context from their READMEs.
- Use clear Markdown formatting. Do not describe the entire project; focus ONLY on the contents and role of THIS directory.
"""

ROOT_PROMPT_TEMPLATE = """
SYSTEM: You are an expert technical writer creating the main `README.md` for an entire software project. Your tone should be welcoming and comprehensive.

USER:
You are generating the main `README.md` for a project.

The user-provided project description is:
"{project_description}"

---
The project's root directory contains the following source code files:
{file_summaries}
---

The project has the following main subdirectories. Use their `README.md` content (provided below) to describe the overall structure of the project:
{subdirectory_readmes}
---

TASK:
Write a comprehensive `README.md` for the entire project. Structure it with the following sections:
- A main title (`# Project: {project_name}`).
- **Overview**: A slightly more detailed version of the user's description, enhanced with context from the files and subdirectories.
- **Project Structure**: A description of the key directories and their roles, using the information from the subdirectory READMEs.
- **Key Features**: Infer and list the key features of the project based on all the provided context.
"""

UPDATE_SUBDIR_PROMPT_TEMPLATE = """
SYSTEM: You are an expert technical writer updating a README.md file for a specific directory. Your tone should be informative and concise. A user has provided a note with instructions.

USER:
You are updating the `README.md` for the directory: `{current_dir_relative}`

The user-provided note with instructions for this update is:
"{user_note}"

The overall project description is:
"{project_description}"
---
This directory contains the following source code files. Use them to describe the specific purpose of this directory:
{file_summaries}
---
This directory also contains the following subdirectories. Use their `README.md` content (provided below) to summarize their roles:
{subdirectory_readmes}
---
Here is the OLD `README.md` content. You must update it based on the new context and the user's note.
---
{existing_readme}
---
TASK:
Rewrite the `README.md` for the `{current_dir_relative}` directory, incorporating the user's note and any new information from the files and subdirectories.
- Start with a heading (e.g., `# Directory: {dir_name}`).
- Use the existing content as a base, but modify it as needed.
- Use clear Markdown formatting. Do not describe the entire project; focus ONLY on the contents and role of THIS directory.
"""

UPDATE_ROOT_PROMPT_TEMPLATE = """
SYSTEM: You are an expert technical writer updating the main `README.md` for an entire software project. Your tone should be welcoming and comprehensive. A user has provided a note with instructions.

USER:
You are updating the main `README.md` for a project.

The user-provided note with instructions for this update is:
"{user_note}"

The user-provided project description is:
"{project_description}"
---
The project's root directory contains the following source code files:
{file_summaries}
---
The project has the following main subdirectories. Use their `README.md` content (provided below) to describe the overall structure of the project:
{subdirectory_readmes}
---
Here is the OLD `README.md` content. You must update it based on the new context and the user's note.
---
{existing_readme}
---
TASK:
Rewrite a comprehensive `README.md` for the entire project. Structure it with the following sections, using the old README as a base but incorporating changes based on the user's note and new context.
- A main title (`# Project: {project_name}`).
- **Overview**: An updated version of the user's description, enhanced with context.
- **Project Structure**: A description of the key directories and their roles.
- **Key Features**: Infer and list key features based on all the provided context.
"""

def no_op_callback(event: str, data: dict):
    pass

class ReadmeGenerator:
    def __init__(self, path_or_url: str, description: str, exclude: List[str], llm_handler: LLMHandler, user_note: str = "", repo_full_name="", progress_callback: Callable[[str, dict], None] = no_op_callback):
        self.path_or_url = path_or_url
        self.description = description
        # Also exclude README.md from being summarized as a file
        self.exclude = exclude + ["README.md"]
        self.llm_handler = llm_handler
        self.user_note = user_note
        self.progress_callback = progress_callback
        self.project_path = None
        self.is_temp_dir = path_or_url.startswith("http")
        self.repo_full_name  = repo_full_name
        
        # --- NEW: Bridge the LLM Handler's logging just like in the orchestrator ---
        def llm_log_wrapper(message: str):
            self.progress_callback("log", {"message": message})
        
        
        self.llm_handler.progress_callback = llm_log_wrapper

    def run(self):
        """Public method to start README generation."""
        try:
            self.project_path = scanner.get_project_path(self.path_or_url)
            self.progress_callback("phase", {"id": "readmes", "name": "Generating READMEs", "status": "in-progress"})
            self.run_with_structured_logging()
            self.progress_callback("phase", {"id": "readmes", "status": "success"})
        except Exception as e:
            self.progress_callback("log", {"message": f"An unexpected error occurred in README generation: {e}"})
            self.progress_callback("phase", {"id": "readmes", "status": "error"})
            raise # Re-raise the exception to be caught by the main handler
        finally:
            if self.is_temp_dir and self.project_path and self.project_path.exists():
                shutil.rmtree(self.project_path, ignore_errors=True)

    def _summarize_py_file(self, file_path: Path) -> str:
        """Extracts the module-level docstring or a placeholder for a Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)
            if docstring:
                # Return just the first line for brevity in the prompt
                return f"`{file_path.name}`: {docstring.strip().splitlines()[0]}"
        except Exception as e:
            self.progress_callback("log", {"message": f"Could not parse docstring from {file_path.name}: {e}"})
        return f"`{file_path.name}`: A Python source file."

    def run_with_structured_logging(self):
        """
        Generates README files for each directory from the bottom up,
        emitting structured events for the UI.
        """
        # Note: The 'run' method from before is now integrated here with structured callbacks.
        if not self.project_path:
             self.project_path = scanner.get_project_path(self.path_or_url)
             
        for dir_path, subdir_names, file_names in os.walk(self.project_path, topdown=False):
            current_dir = Path(dir_path)
            
            # Skip excluded directories
            if scanner.is_excluded(current_dir, self.exclude, self.project_path):
                continue

            rel_path = current_dir.relative_to(self.project_path).as_posix()
            dir_id = rel_path if rel_path != "." else "root"
            dir_name_display = rel_path if rel_path != "." else "Project Root"

            self.progress_callback("subtask", {"parentId": "readmes", "listId": "readme-dir-list", "id": dir_id, "name": f"Directory: {dir_name_display}", "status": "in-progress"})
            
            try:
                # 1. Gather context from files in the current directory
                file_summaries = self._gather_file_summaries(current_dir, file_names)
                # 2. Gather context from subdirectories' READMEs (which are now generated)
                subdirectory_readmes = self._gather_subdirectory_readmes(current_dir, subdir_names)

                # 3. Check for an existing README to update
                existing_readme_content = None
                existing_readme_path = current_dir / "README.md"
                if existing_readme_path.exists():
                    with open(existing_readme_path, "r", encoding="utf-8") as f:
                        existing_readme_content = f.read()

                # 4. Build the prompt
                prompt = self._build_prompt(current_dir, file_summaries, subdirectory_readmes, existing_readme_content)

                # 5. Generate README content via LLM
                generated_content = self.llm_handler.generate_text_response(prompt)
                
                # 6. Write the README.md file
                with open(current_dir / "README.md", "w", encoding="utf-8") as f:
                    f.write(generated_content)
                
                self.progress_callback("subtask", {"parentId": "readmes", "id": dir_id, "status": "success"})

            except Exception as e:
                self.progress_callback("log", {"message": f"Failed to generate README for {dir_name_display}: {e}"})
                self.progress_callback("subtask", {"parentId": "readmes", "id": dir_id, "status": "error"})


    def _gather_file_summaries(self, current_dir: Path, file_names: List[str]) -> str:
        file_summaries_list = []
        for fname in file_names:
            if fname.endswith(".py"):
               file_path = current_dir / fname
               if not scanner.is_excluded(file_path, self.exclude, self.project_path):
                   file_summaries_list.append(self._summarize_py_file(file_path))
        return "\n".join(file_summaries_list) or "No Python source files in this directory."

    def _gather_subdirectory_readmes(self, current_dir: Path, subdir_names: List[str]) -> str:
        subdir_readmes_list = []
        for sub_name in subdir_names:
            readme_path = current_dir / sub_name / "README.md"
            if readme_path.exists():
                with open(readme_path, "r", encoding="utf-8") as f:
                    content = f.read()
                subdir_readmes_list.append(f"--- Subdirectory: `{sub_name}` ---\n{content}\n")
        return "\n".join(subdir_readmes_list) or "No subdirectories with READMEs."

    def _build_prompt(self, current_dir: Path, file_summaries: str, subdirectory_readmes: str, existing_readme: str | None) -> str:
        is_root = current_dir == self.project_path
        common_args = {
            "project_description": self.description,
            "file_summaries": file_summaries,
            "subdirectory_readmes": subdirectory_readmes,
            "user_note": self.user_note or "No specific instructions provided.",
        }

        if is_root:
            template = UPDATE_ROOT_PROMPT_TEMPLATE if existing_readme else ROOT_PROMPT_TEMPLATE
            args = {**common_args, "project_name": self.repo_full_name if self.repo_full_name else self.project_path.name}
            if existing_readme: args["existing_readme"] = existing_readme
        else: # is subdirectory
            template = UPDATE_SUBDIR_PROMPT_TEMPLATE if existing_readme else SUBDIR_PROMPT_TEMPLATE
            args = {**common_args, "current_dir_relative": current_dir.relative_to(self.project_path).as_posix(), "dir_name": current_dir.name}
            if existing_readme: args["existing_readme"] = existing_readme
        
        return template.format(**args)