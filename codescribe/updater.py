# codescribe/updater.py

import ast
from pathlib import Path
from typing import Dict, Callable

# Helper no-op function for default callback
def _no_op_log(message: str):
    pass

class DocstringInserter(ast.NodeTransformer):
    def __init__(self, docstrings: Dict[str, str]):
        self.docstrings = docstrings
        self.current_class = None

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.current_class = node.name
        if node.name in self.docstrings:
            self._insert_docstring(node, self.docstrings[node.name])
        self.generic_visit(node)
        self.current_class = None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        key = f"{self.current_class}.{node.name}" if self.current_class else node.name
        if key in self.docstrings:
            self._insert_docstring(node, self.docstrings[key])
        return node

    def _insert_docstring(self, node, docstring_text):
        docstring_node = ast.Expr(value=ast.Constant(value=docstring_text))
        if ast.get_docstring(node):
            node.body[0] = docstring_node
        else:
            node.body.insert(0, docstring_node)

def update_file_with_docstrings(file_path: Path, docstrings: Dict[str, str], log_callback: Callable[[str], None] = print):
    """
    Parses a Python file, inserts docstrings for functions/classes, and overwrites the file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        transformer = DocstringInserter(docstrings)
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)
        
        new_source_code = ast.unparse(new_tree)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source_code)
        log_callback(f"Successfully updated {file_path.name} with new docstrings.")

    except Exception as e:
        log_callback(f"Error updating file {file_path.name}: {e}")

def update_module_docstring(file_path: Path, docstring: str, log_callback: Callable[[str], None] = print):
    """
    Parses a Python file, adds or replaces the module-level docstring, and overwrites the file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
        
        tree = ast.parse(source_code)
        
        # Create the new docstring node
        new_docstring_node = ast.Expr(value=ast.Constant(value=docstring))
        
        # Check if a module docstring already exists
        if ast.get_docstring(tree):
            # Replace the existing docstring node
            tree.body[0] = new_docstring_node
        else:
            # Insert the new docstring node at the beginning
            tree.body.insert(0, new_docstring_node)
            
        ast.fix_missing_locations(tree)
        new_source_code = ast.unparse(tree)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source_code)
        log_callback(f"Successfully added/updated module docstring for {file_path.name}.")

    except Exception as e:
        log_callback(f"Error updating module docstring for {file_path.name}: {e}")