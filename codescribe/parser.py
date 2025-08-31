"""This module provides functions to parse Python files and build a dependency graph."""
import ast
from pathlib import Path
from typing import List, Set, Callable
import networkx as nx

def resolve_import_path(current_file: Path, module_name: str, level: int, project_root: Path) -> Path | None:
    """Resolve the import path of a module given the current file, module name, and level."""
    if level > 0:
        base_path = current_file.parent
        for _ in range(level - 1):
            base_path = base_path.parent
        module_path = base_path / Path(*module_name.split('.'))
    else:
        module_path = project_root / Path(*module_name.split('.'))
    if module_path.with_suffix('.py').exists():
        return module_path.with_suffix('.py')
    if (module_path / '__init__.py').exists():
        return module_path / '__init__.py'
    return None

def build_dependency_graph(file_paths: List[Path], project_root: Path, log_callback: Callable[[str], None]=print) -> nx.DiGraph:
    """Builds a dependency graph from a list of Python files. Uses a callback for logging warnings."""
    graph = nx.DiGraph()
    path_map = {p.stem: p for p in file_paths}
    for file_path in file_paths:
        graph.add_node(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        dep_path = resolve_import_path(file_path, node.module, node.level, project_root)
                        if dep_path and dep_path in file_paths:
                            graph.add_edge(file_path, dep_path)
        except Exception as e:
            log_callback(f'Warning: Could not parse {file_path.name} for dependencies. Skipping. Error: {e}')
    return graph