"""
Base Coding Tools
=================

Core development tools for software engineering agents.
Includes file operations, code analysis, project management, and terminal execution.
"""

from langchain_core.tools import tool
import os
import re
import json
import ast
import subprocess
from pathlib import Path
from typing import Optional

# Note: Shell execution is provided by ShellToolMiddleware in base.py
# No need for duplicate shell tools here


@tool
def code_analyzer(code: str, language: str = "python") -> str:
    """
    Analyze code quality and structure.
    
    Args:
        code: Source code to analyze
        language: Programming language
        
    Returns:
        Analysis results
    """
    try:
        if language.lower() == "python":
            tree = ast.parse(code)
            
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
            
            lines = code.split('\n')
            total_lines = len(lines)
            code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
            
            return f"""Code Analysis:
- Language: {language}
- Total lines: {total_lines}
- Code lines: {code_lines}
- Functions: {len(functions)} - {', '.join(functions[:5])}{'...' if len(functions) > 5 else ''}
- Classes: {len(classes)} - {', '.join(classes[:5])}{'...' if len(classes) > 5 else ''}
- Imports: {len(imports)} - {', '.join(imports[:5])}{'...' if len(imports) > 5 else ''}"""
        
        else:
            lines = code.split('\n')
            return f"Basic analysis for {language}: {len(lines)} lines"
    
    except Exception as e:
        return f"Error analyzing code: {str(e)}"


@tool
def syntax_checker(code: str, language: str) -> str:
    """
    Check code syntax for errors.
    
    Args:
        code: Source code to check
        language: Programming language
        
    Returns:
        Syntax check results
    """
    try:
        if language.lower() == "python":
            ast.parse(code)
            return "✓ Syntax is valid"
        else:
            return f"Syntax checking for {language} not implemented yet"
    
    except SyntaxError as e:
        return f"✗ Syntax Error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def regex_helper(pattern: str, text: str, operation: str = "findall") -> str:
    """
    Regex operations on text.
    
    Args:
        pattern: Regex pattern
        text: Text to search
        operation: Operation type (findall, search, match, split, sub)
        
    Returns:
        Operation results
    """
    try:
        if operation == "findall":
            matches = re.findall(pattern, text)
            return f"Found {len(matches)} matches: {matches}"
        elif operation == "search":
            match = re.search(pattern, text)
            return f"Match found: {match.group()}" if match else "No match found"
        elif operation == "match":
            match = re.match(pattern, text)
            return f"Match at start: {match.group()}" if match else "No match at start"
        elif operation == "split":
            parts = re.split(pattern, text)
            return f"Split into {len(parts)} parts: {parts}"
        else:
            return f"Unknown operation: {operation}"
    
    except Exception as e:
        return f"Regex error: {str(e)}"


@tool
def json_formatter(json_string: str, operation: str = "format") -> str:
    """
    Format or validate JSON.
    
    Args:
        json_string: JSON string
        operation: Operation (format, validate, minify)
        
    Returns:
        Formatted JSON or error
    """
    try:
        data = json.loads(json_string)
        
        if operation == "format":
            return json.dumps(data, indent=2)
        elif operation == "minify":
            return json.dumps(data, separators=(',', ':'))
        elif operation == "validate":
            return "✓ Valid JSON"
        else:
            return json.dumps(data, indent=2)
    
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def read_file_content(file_path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
    """
    Read file contents with optional line range.
    
    Args:
        file_path: Path to file
        start_line: Starting line (1-indexed)
        end_line: Ending line (None for end of file)
        
    Returns:
        File contents or error
    """
    try:
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if start_line < 1:
            start_line = 1
        if end_line is None or end_line <= 0:
            end_line = len(lines)
        
        if start_line > len(lines):
            return f"Error: Start line {start_line} beyond file length {len(lines)}"
        
        content = ''.join(lines[start_line-1:end_line])
        return f"File: {file_path} (lines {start_line}-{min(end_line, len(lines))})\n{'='*60}\n{content}"
    
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file_content(file_path: str, content: str, mode: str = "w") -> str:
    """
    Write content to a file.
    
    Args:
        file_path: Path to file
        content: Content to write
        mode: Write mode ('w' = overwrite, 'a' = append)
        
    Returns:
        Success or error message
    """
    try:
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        
        with open(file_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        action = "appended to" if mode == "a" else "written to"
        return f"✓ Content {action} {file_path} ({len(content)} characters)"
    
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def get_file_tree(directory_path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> str:
    """
    Get a tree view of files and directories.
    
    Args:
        directory_path: Directory to scan
        max_depth: Maximum depth to traverse
        show_hidden: Include hidden files
        
    Returns:
        Tree structure
    """
    try:
        def build_tree(path: Path, prefix: str = "", depth: int = 0) -> str:
            if depth > max_depth:
                return ""
            
            tree = ""
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                if not show_hidden:
                    items = [i for i in items if not i.name.startswith('.')]
                
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    tree += f"{prefix}{current_prefix}{item.name}\n"
                    
                    if item.is_dir() and depth < max_depth:
                        extension = "    " if is_last else "│   "
                        tree += build_tree(item, prefix + extension, depth + 1)
            except PermissionError:
                tree += f"{prefix}[Permission Denied]\n"
            
            return tree
        
        path = Path(directory_path).resolve()
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        result = f"{path.name}/\n"
        result += build_tree(path)
        return result
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def list_directory_contents(directory_path: str, file_types: Optional[str] = None, show_hidden: bool = False) -> str:
    """
    List files and directories with details.
    
    Args:
        directory_path: Directory to list
        file_types: Filter by extensions (e.g., "py,js,txt")
        show_hidden: Include hidden files
        
    Returns:
        Directory listing
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        if not show_hidden:
            items = [i for i in items if not i.name.startswith('.')]
        
        if file_types:
            extensions = [f".{ext.strip()}" for ext in file_types.split(',')]
            items = [i for i in items if i.is_dir() or i.suffix in extensions]
        
        result = f"Directory: {directory_path}\n{'='*60}\n"
        
        dirs = [i for i in items if i.is_dir()]
        files = [i for i in items if i.is_file()]
        
        if dirs:
            result += "\nDirectories:\n"
            for d in dirs:
                result += f"  📁 {d.name}/\n"
        
        if files:
            result += "\nFiles:\n"
            for f in files:
                size = f.stat().st_size
                result += f"  📄 {f.name} ({size} bytes)\n"
        
        result += f"\nTotal: {len(dirs)} directories, {len(files)} files"
        return result
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def search_files(directory_path: str, pattern: str, file_types: Optional[str] = None) -> str:
    """
    Search for files by name pattern.
    
    Args:
        directory_path: Directory to search
        pattern: Filename pattern (glob or regex)
        file_types: Filter by extensions
        
    Returns:
        List of matching files
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        matches = list(path.rglob(pattern))
        
        if file_types:
            extensions = [f".{ext.strip()}" for ext in file_types.split(',')]
            matches = [m for m in matches if m.suffix in extensions]
        
        if not matches:
            return f"No files found matching '{pattern}'"
        
        result = f"Found {len(matches)} files matching '{pattern}':\n"
        for m in matches[:50]:
            result += f"  {m.relative_to(path)}\n"
        
        if len(matches) > 50:
            result += f"\n... and {len(matches) - 50} more files"
        
        return result
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def search_in_files(directory_path: str, search_text: str, file_types: str = "py,js,txt,md,json") -> str:
    """
    Search for text within files (grep-like).
    
    Args:
        directory_path: Directory to search
        search_text: Text to find
        file_types: File extensions to search
        
    Returns:
        Matching lines with file locations
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        extensions = [f".{ext.strip()}" for ext in file_types.split(',')]
        results = []
        
        for ext in extensions:
            for file_path in path.rglob(f"*{ext}"):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if search_text in line:
                                rel_path = file_path.relative_to(path)
                                results.append(f"{rel_path}:{line_num}: {line.strip()}")
                except:
                    pass
        
        if not results:
            return f"No matches found for '{search_text}'"
        
        result = f"Found {len(results)} matches for '{search_text}':\n"
        result += "\n".join(results[:50])
        
        if len(results) > 50:
            result += f"\n\n... and {len(results) - 50} more matches"
        
        return result
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_file_info(file_path: str) -> str:
    """
    Get detailed file information.
    
    Args:
        file_path: Path to file
        
    Returns:
        File metadata
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        stats = path.stat()
        
        return f"""File: {file_path}
{'='*60}
Size: {stats.st_size} bytes
Type: {'Directory' if path.is_dir() else 'File'}
Extension: {path.suffix if path.suffix else 'None'}
Modified: {stats.st_mtime}
Readable: {os.access(file_path, os.R_OK)}
Writable: {os.access(file_path, os.W_OK)}
"""
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def create_project_structure(project_name: str, project_type: str, base_path: str = ".") -> str:
    """
    Create a project directory structure.
    
    Args:
        project_name: Name of the project
        project_type: Type (python, javascript, react, etc.)
        base_path: Base directory
        
    Returns:
        Success or error message
    """
    try:
        project_path = Path(base_path) / project_name
        
        if project_type.lower() == "python":
            dirs = [
                project_path / "src",
                project_path / "tests",
                project_path / "docs",
            ]
            files = {
                project_path / "README.md": f"# {project_name}\n\nPython project",
                project_path / "requirements.txt": "",
                project_path / "src" / "__init__.py": "",
            }
        elif project_type.lower() == "javascript":
            dirs = [
                project_path / "src",
                project_path / "tests",
            ]
            files = {
                project_path / "README.md": f"# {project_name}\n\nJavaScript project",
                project_path / "package.json": json.dumps({"name": project_name, "version": "1.0.0"}, indent=2),
            }
        else:
            return f"Unknown project type: {project_type}"
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        for file_path, content in files.items():
            file_path.write_text(content)
        
        return f"✓ Created {project_type} project '{project_name}' at {project_path}"
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def git_helper(command: str, repository_path: str = ".") -> str:
    """
    Execute git commands safely.
    
    Args:
        command: Git command (status, log, diff, branch)
        repository_path: Path to git repository
        
    Returns:
        Git command output
    """
    try:
        safe_commands = ['status', 'log', 'diff', 'branch', 'show']
        
        if command not in safe_commands:
            return f"Unsafe command '{command}'. Allowed: {', '.join(safe_commands)}"
        
        result = subprocess.run(
            ['git', command],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Git error: {result.stderr}"
    
    except FileNotFoundError:
        return "Git not found. Install git first."
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def get_python_info(query: str = "version") -> str:
    """
    Get Python environment information.
    
    Args:
        query: Info type (version, path, packages, sys_path)
        
    Returns:
        Python environment details
    """
    try:
        import sys
        
        if query == "version":
            return f"Python {sys.version}"
        elif query == "path":
            return f"Python executable: {sys.executable}"
        elif query == "packages":
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        elif query == "sys_path":
            return "Python module search paths:\n" + "\n".join(sys.path)
        else:
            return f"Unknown query '{query}'. Use: version, path, packages, sys_path"
    
    except Exception as e:
        return f"Error: {str(e)}"

# NOTE: Shell command execution is provided by ShellToolMiddleware
# When you set enable_shell_tool=True in base.py, LangChain automatically
# adds a persistent shell tool to the agent. No need for duplicate tools here.
# The ShellToolMiddleware provides:
# - Persistent shell sessions (cd persists, env vars persist)
# - Proper workspace isolation
# - Execution policies (host/docker/sandbox)
# - Better security and resource management

@tool
def propose_file_create(file_path: str, content: str, reason: str = "") -> str:
    """Propose file creation (requires approval).
    
    Args:
        file_path: Path for new file
        content: File content
        reason: Reason for creation
        
    Returns:
        Proposal for review
    """
    preview = content[:200] + "..." if len(content) > 200 else content
    exists = "EXISTS - would overwrite!" if Path(file_path).exists() else "new file"
    
    return f"""📝 PROPOSE FILE CREATE
{'='*60}
File: {file_path} ({exists})
Reason: {reason or 'File creation'}

Content Preview:
{preview}

Size: {len(content)} characters
⚠️  Use write_file_content() to actually create this file."""


@tool
def propose_file_edit(file_path: str, changes: str, reason: str = "") -> str:
    """Propose file edit (requires approval).
    
    Args:
        file_path: File to edit
        changes: Description of changes
        reason: Reason for edit
        
    Returns:
        Proposal for review
    """
    exists = "EXISTS" if Path(file_path).exists() else "DOES NOT EXIST"
    
    return f"""✏️  PROPOSE FILE EDIT
{'='*60}
File: {file_path} ({exists})
Reason: {reason or 'File modification'}

Changes:
{changes}

⚠️  Use write_file_content() to actually modify this file."""


@tool
def propose_file_delete(file_path: str, reason: str = "") -> str:
    """Propose file deletion (requires approval).
    
    Args:
        file_path: File to delete
        reason: Reason for deletion
        
    Returns:
        Proposal for review
    """
    path = Path(file_path)
    exists = "EXISTS" if path.exists() else "DOES NOT EXIST"
    size = path.stat().st_size if path.exists() else 0
    
    return f"""🗑️  PROPOSE FILE DELETE
{'='*60}
File: {file_path} ({exists})
Size: {size} bytes
Reason: {reason or 'File removal'}

⚠️  WARNING: This action cannot be undone!
⚠️  Use os.remove() carefully to actually delete."""
