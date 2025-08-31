import os
import re
from pathlib import Path
from typing import List
import git
import tempfile
import shutil

def is_excluded(path: Path, exclude_patterns: List[str], project_root: Path) -> bool:
    """Check if a path matches any of the exclusion patterns."""
    # Convert path to a string with forward slashes for consistency
    relative_path_str = path.relative_to(project_root).as_posix()

    # --- NEW: Default rule to ignore dot-prefixed files/folders ---
    # Check if any part of the path starts with a dot.
    if any(part.startswith('.') for part in path.relative_to(project_root).parts):
        return True

    for pattern in exclude_patterns:
        try:
            # Try to treat pattern as regex
            if re.search(pattern, relative_path_str):
                return True
        except re.error:
            # Fallback to simple string contains for non-regex patterns
            # This is useful for direct path matches from the checkboxes
            if pattern in relative_path_str:
                return True
    return False

def scan_project(project_path: Path, exclude_patterns: List[str]) -> List[Path]:
    """Scans a project directory for Python files, excluding specified patterns."""
    py_files = []
    # Use os.walk to respect directory exclusions more easily
    for root, dirs, files in os.walk(project_path, topdown=True):
        root_path = Path(root)
        
        # --- NEW: Filter directories in place to avoid walking them ---
        original_dirs = dirs[:] # copy to iterate over
        dirs[:] = [d for d in original_dirs if not is_excluded(root_path / d, exclude_patterns, project_path)]

        for file in files:
            if file.endswith('.py'):
                file_path = root_path / file
                if not is_excluded(file_path, exclude_patterns, project_path):
                    py_files.append(file_path)
    return py_files


def get_project_path(path_or_url: str) -> Path:
    """Clones a repo if a URL is given, otherwise returns the Path object for a local directory."""
    if path_or_url.startswith("http") or path_or_url.startswith("git@"):
        temp_dir = tempfile.mkdtemp()
        print(f"Cloning repository {path_or_url} into {temp_dir}...")
        try:
            git.Repo.clone_from(path_or_url, temp_dir)
            return Path(temp_dir)
        except Exception as e:
            shutil.rmtree(temp_dir)
            raise RuntimeError(f"Failed to clone repository: {e}")
    else:
        path = Path(path_or_url)
        if not path.is_dir():
            raise FileNotFoundError(f"The specified path does not exist or is not a directory: {path}")
        return path