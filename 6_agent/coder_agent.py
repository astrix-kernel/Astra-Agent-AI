import os
import subprocess
from pathlib import Path

class CoderAgent:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    def scan_bugs(self, file_path):
        """Scans a file for syntax errors and potential bugs."""
        full_path = self.workspace / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"
        
        if file_path.endswith('.py'):
            # Use Python's internal compiler to check syntax
            result = subprocess.run(['python3', '-m', 'py_compile', str(full_path)], capture_output=True, text=True)
            if result.returncode != 0:
                return f"BUG FOUND in {file_path}:\n{result.stderr}"
            return f"No syntax bugs found in {file_path}."
        
        return "Auto-scan only supports .py files for now."

    def remove_unused_code(self, file_path, unused_pattern):
        """Removes specific lines of code (e.g., print statements or dead code)."""
        full_path = self.workspace / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"
        
        with open(full_path, 'r') as f:
            lines = f.readlines()
        
        new_lines = [line for line in lines if unused_pattern not in line]
        
        with open(full_path, 'w') as f:
            f.writelines(new_lines)
            
        return f"Successfully removed lines containing '{unused_pattern}' from {file_path}."

    def auto_build(self, build_command="make -j4"):
        """Runs a build command in the workspace."""
        try:
            result = subprocess.run(build_command, shell=True, cwd=self.workspace, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return f"BUILD SUCCESS:\n{result.stdout[-500:]}"
            else:
                return f"BUILD FAILED:\n{result.stderr[-1000:]}"
        except subprocess.TimeoutExpired:
            return "Build timed out."

    def write_code(self, file_path, content):
        """Writes or overwrites a file."""
        full_path = self.workspace / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return f"Code written to {file_path}."

# Export a singleton instance
coder = CoderAgent(os.getenv("ASTRIX_WORKSPACE", "."))
