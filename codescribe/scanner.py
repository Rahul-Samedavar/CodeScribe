
import os
import re
from pathlib import Path
from typing import List, Callable # Add Callable
import git
import tempfile
import shutil

# ... is_excluded function is unchanged ...
def is_excluded(path: Path, exclude_patterns: List[str], project_root: Path) -> bool:
    relative_path_str = path.relative_to(project_root).as_posix()
    if any(part.startswith('.') for part in path.relative_to(project_root).parts):
        return True
    for pattern in exclude_patterns:
        try:
            if re.search(pattern, relative_path_str):
                return True
        except re.error:
            if pattern in relative_path_str:
                return True
    return False

# ... scan_project function is unchanged ...
def scan_project(project_path: Path, exclude_patterns: List[str]) -> List[Path]:
    py_files = []
    for root, dirs, files in os.walk(project_path, topdown=True):
        root_path = Path(root)
        original_dirs = dirs[:]
        dirs[:] = [d for d in original_dirs if not is_excluded(root_path / d, exclude_patterns, project_path)]
        for file in files:
            if file.endswith('.py'):
                file_path = root_path / file
                if not is_excluded(file_path, exclude_patterns, project_path):
                    py_files.append(file_path)
    return py_files

def get_project_path(path_or_url: str, log_callback: Callable[[str], None] = print) -> Path:
    """
    Clones a repo if a URL is given, otherwise returns the Path object.
    Uses a callback for logging.
    """
    if path_or_url.startswith("http") or path_or_url.startswith("git@"):
        temp_dir = tempfile.mkdtemp()
        # Use the callback instead of print
        log_callback(f"Cloning repository {path_or_url} into temporary directory...")
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
