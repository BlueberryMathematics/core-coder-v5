"""
Dynamic Tool Management System (Toolbox)
========================================

A comprehensive system for creating, storing, validating, and managing tools dynamically.
Supports LLM-generated tools, manual tool creation, and automatic registration.

🔗 UNIFIED ARCHITECTURE (Two Systems, One Interface):

1. **Predefined Tools (tools.py)**
   - Battle-tested tools maintained in langchain-agent-base package
   - get_coding_tools(), get_math_tools(), get_science_tools()
   - Auto-registered into toolbox on initialization
   - Updated via package upgrades (pip install --upgrade)
   
2. **Dynamic Toolbox (toolbox.py)**  
   - LLM-generated custom tools
   - User-created manual tools
   - Stored in toolbox/<category>/*.py files
   - Persists across sessions

**Both systems unified via ToolboxManager:**
- Predefined tools automatically registered on module import
- Dynamic tools loaded from toolbox directory
- Both accessible via get_tools_by_category('coding')
- UI toolbox selection works for both types

**Why This Design?**
- ✅ Package updates improve all exported agents (predefined tools)
- ✅ Custom tools per agent/friend (dynamic toolbox)
- ✅ Easy migration when base package updates
- ✅ Clean separation: stable vs experimental tools

Features:
- Dynamic tool creation from code strings
- Tool validation and testing
- Persistent storage to Python files
- Automatic discovery and registration
- Version control for tools
- Category-based organization
- Duplicate detection
- Integration with agent system

Usage:
    from .toolbox import ToolboxManager, create_tool_from_code
    
    # Initialize toolbox (auto-registers predefined tools)
    toolbox = ToolboxManager()
    
    # Get predefined coding tools
    coding_tools = toolbox.get_tools_by_category("coding")
    # Returns: [code_analyzer, regex_helper, json_formatter, ...]
    
    # Add LLM-generated tool
    tool_code = \"\"\"
    @tool
    def my_custom_tool(x: int, y: int) -> str:
        '''Add two numbers and return result.'''
        return f"Result: {x + y}"
    \"\"\"
    toolbox.add_tool_from_code(tool_code, category="math", author="llm")
    
    # Get all math tools (predefined + custom)
    all_math_tools = toolbox.get_tools_by_category("math")
    
    # Add tools to agent
    agent.add_tools(all_math_tools)
"""

import os
import ast
import inspect
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import traceback

from langchain_core.tools import tool, Tool


@dataclass
class ToolMetadata:
    """Metadata for a tool in the toolbox."""
    name: str
    description: str
    category: str
    author: str = "unknown"
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    file_path: Optional[str] = None  # None for predefined tools
    source: str = "custom"  # "predefined" or "custom" or "generated"
    function_signature: str = ""
    code_hash: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    tested: bool = False
    test_results: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


class ToolValidator:
    """Validates tool code for safety and correctness."""
    
    # Dangerous operations to block
    FORBIDDEN_IMPORTS = {
        'os.system', 'subprocess', 'eval', 'exec', '__import__',
        'compile', 'open', 'file'  # Can be allowed with restrictions
    }
    
    # Allowed imports for tools
    ALLOWED_IMPORTS = {
        'math', 'json', 're', 'typing', 'dataclasses',
        'langchain_core.tools', 'datetime', 'collections',
        'sympy', 'numpy', 'scipy', 'pandas', 'requests'
    }
    
    @staticmethod
    def validate_code(code: str) -> Tuple[bool, str, Optional[ast.AST]]:
        """
        Validate tool code for syntax and safety.
        
        Returns:
            (is_valid, message, ast_tree)
        """
        try:
            # Parse the code
            tree = ast.parse(code)
            
            # Check for dangerous operations
            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in ToolValidator.ALLOWED_IMPORTS:
                            return False, f"Forbidden import: {alias.name}", None
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module not in ToolValidator.ALLOWED_IMPORTS:
                        # Check if it's a sub-import of allowed modules
                        parent = node.module.split('.')[0]
                        if parent not in ToolValidator.ALLOWED_IMPORTS:
                            return False, f"Forbidden import: {node.module}", None
                
                # Check for eval/exec
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', '__import__']:
                            return False, f"Forbidden function: {node.func.id}", None
            
            # Check for @tool decorator
            has_tool_decorator = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == 'tool':
                            has_tool_decorator = True
                            break
                        elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                            if decorator.func.id == 'tool':
                                has_tool_decorator = True
                                break
            
            if not has_tool_decorator:
                return False, "Tool must have @tool decorator", None
            
            return True, "Code is valid", tree
            
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}", None
        except Exception as e:
            return False, f"Validation error: {str(e)}", None
    
    @staticmethod
    def extract_tool_info(code: str, tree: ast.AST = None) -> Dict[str, Any]:
        """Extract tool metadata from code."""
        if tree is None:
            tree = ast.parse(code)
        
        info = {
            'name': '',
            'description': '',
            'parameters': {},
            'dependencies': []
        }
        
        # Find the tool function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if it has @tool decorator
                has_tool = any(
                    (isinstance(d, ast.Name) and d.id == 'tool') or
                    (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'tool')
                    for d in node.decorator_list
                )
                
                if has_tool:
                    info['name'] = node.name
                    info['description'] = ast.get_docstring(node) or "No description"
                    
                    # Extract parameters
                    for arg in node.args.args:
                        param_name = arg.arg
                        param_type = "Any"
                        
                        if arg.annotation:
                            if isinstance(arg.annotation, ast.Name):
                                param_type = arg.annotation.id
                            elif isinstance(arg.annotation, ast.Subscript):
                                param_type = ast.unparse(arg.annotation)
                        
                        info['parameters'][param_name] = param_type
                    
                    break
        
        # Extract imports as dependencies
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    info['dependencies'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    info['dependencies'].append(node.module)
        
        return info


class ToolboxManager:
    """
    Manages a collection of dynamically created tools.
    Provides storage, retrieval, validation, and organization.
    """
    
    def __init__(self, 
                 toolbox_dir: Optional[str] = None,
                 registry_file: str = "tool_registry.json",
                 auto_load: bool = True):
        """
        Initialize the toolbox manager.
        
        Args:
            toolbox_dir: Directory to store tool files
            registry_file: JSON file to store tool metadata
            auto_load: Automatically load existing tools on init
        """
        self.toolbox_dir = self._resolve_toolbox_dir(toolbox_dir)
        
        # Category directories (created lazily; see _ensure_dirs())
        self.categories = ['math', 'science', 'coding', 'rag', 'business', 'custom', 'generated']
        
        self.registry_file = self.toolbox_dir / registry_file
        self.registry: Dict[str, ToolMetadata] = {}
        self.tools: Dict[str, Callable] = {}  # name -> function
        
        if auto_load:
            # IMPORTANT: Avoid creating directories on startup.
            # Only load dynamic tools if the toolbox directory already exists.
            if self.toolbox_dir.exists():
                self._load_registry()
                self._load_tools()
            
        # 🔗 BRIDGE: Auto-register predefined tools from tools.py
        # This unifies the two systems:
        # - tools.py: Battle-tested predefined tools
        # - toolbox.py: Dynamic LLM-generated tools
        # Both accessible via get_tools_by_category()
        self._register_predefined_tools()

    @staticmethod
    def _resolve_toolbox_dir(toolbox_dir: Optional[str]) -> Path:
        """
        Resolve toolbox directory location.
        
        Goals:
        - Do NOT depend on current working directory by default (prevents littering random projects)
        - Allow explicit override via parameter or environment variables
        - Preserve backwards-compatibility if an existing ./toolbox is present
        """
        # 1) Explicit parameter wins
        if toolbox_dir:
            return Path(toolbox_dir).expanduser()
        
        # 2) Environment variable overrides
        env_override = (
            os.getenv("CORE_CODER_TOOLBOX_DIR")
            or os.getenv("LANGCHAIN_AGENT_BASE_TOOLBOX_DIR")
            or os.getenv("TOOLBOX_DIR")
        )
        if env_override:
            return Path(env_override).expanduser()
        
        # 3) Back-compat: if an existing local toolbox is present, use it
        cwd_toolbox = Path.cwd() / "toolbox"
        if (cwd_toolbox / "tool_registry.json").exists():
            return cwd_toolbox
        
        # 4) Default: user state directory (XDG-friendly) + langchain-agent-base/toolbox
        # Use "state" because this is persistent user-generated agent state.
        xdg_state = os.getenv("XDG_STATE_HOME")
        if xdg_state:
            base = Path(xdg_state).expanduser()
        else:
            base = Path.home() / ".local" / "state"
        return base / "langchain-agent-base" / "toolbox"

    def _ensure_dirs(self):
        """Create toolbox directory structure if needed (lazy)."""
        self.toolbox_dir.mkdir(parents=True, exist_ok=True)
        
        # Create category directories
        for category in self.categories:
            (self.toolbox_dir / category).mkdir(exist_ok=True)
    
    def _load_registry(self):
        """Load tool registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    data = json.load(f)
                    self.registry = {
                        name: ToolMetadata(**meta) 
                        for name, meta in data.items()
                    }
            except Exception as e:
                print(f"⚠️  Error loading registry: {e}")
    
    def _save_registry(self):
        """Save tool registry to disk."""
        try:
            self._ensure_dirs()
            with open(self.registry_file, 'w') as f:
                data = {
                    name: asdict(meta) 
                    for name, meta in self.registry.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving registry: {e}")
    
    def _load_tools(self):
        """Load all tools from toolbox directory."""
        for category in self.categories:
            category_dir = self.toolbox_dir / category
            for file_path in category_dir.glob("*.py"):
                if file_path.name == "__init__.py":
                    continue
                
                try:
                    # Read file
                    code = file_path.read_text()
                    
                    # Execute in isolated namespace
                    namespace = {'tool': tool}
                    exec(code, namespace)
                    
                    # Find tool functions
                    for name, obj in namespace.items():
                        if callable(obj) and hasattr(obj, 'name'):
                            self.tools[obj.name] = obj
                
                except Exception as e:
                    print(f"⚠️  Error loading tool from {file_path}: {e}")
    
    def _register_predefined_tools(self):
        """
        Register predefined tools from base toolbox modules.
        
        This bridges the two tool systems:
        1. Base toolboxes (base_coding_tools.py, base_math_tools.py, etc.) - Predefined tools
        2. Dynamic toolbox (toolbox.py) - LLM-generated, custom tools
        
        After this registration, UI toolbox selection works correctly:
        - toolboxes: ['coding'] → get_coding_tools() from base_coding_tools.py
        - toolboxes: ['math'] → get_math_tools() from base_math_tools.py
        - toolboxes: ['science'] → get_science_tools() from base_science_tools.py
        - toolboxes: ['rag'] → get_rag_tools() from base_rag_tools.py
        """
        try:
            from tools import get_coding_tools, get_math_tools, get_science_tools, get_rag_tools
            
            # Register coding tools
            coding_tools = get_coding_tools()
            for tool_func in coding_tools:
                if tool_func.name not in self.tools:
                    self.tools[tool_func.name] = tool_func
                    # Don't duplicate in registry/files (already in tools.py)
                    if tool_func.name not in self.registry:
                        self.registry[tool_func.name] = ToolMetadata(
                            name=tool_func.name,
                            description=tool_func.description or "Coding tool",
                            category="coding",
                            author="langchain-agent-base",
                            version="1.0.0",
                            created_at=datetime.now().isoformat(),
                            source="predefined",  # Mark as predefined
                            file_path=None,  # No file needed
                            dependencies=[],
                            tags=["predefined", "coding"]
                        )
            
            # Register math tools
            math_tools = get_math_tools()
            for tool_func in math_tools:
                if tool_func.name not in self.tools:
                    self.tools[tool_func.name] = tool_func
                    if tool_func.name not in self.registry:
                        self.registry[tool_func.name] = ToolMetadata(
                            name=tool_func.name,
                            description=tool_func.description or "Math tool",
                            category="math",
                            author="langchain-agent-base",
                            version="1.0.0",
                            created_at=datetime.now().isoformat(),
                            source="predefined",
                            file_path=None,
                            dependencies=[],
                            tags=["predefined", "math"]
                        )
            
            # Register science tools
            science_tools = get_science_tools()
            for tool_func in science_tools:
                if tool_func.name not in self.tools:
                    self.tools[tool_func.name] = tool_func
                    if tool_func.name not in self.registry:
                        self.registry[tool_func.name] = ToolMetadata(
                            name=tool_func.name,
                            description=tool_func.description or "Science tool",
                            category="science",
                            author="langchain-agent-base",
                            version="1.0.0",
                            created_at=datetime.now().isoformat(),
                            source="base_science_tools",
                            file_path=None,
                            dependencies=[],
                            tags=["predefined", "science", "base_toolbox"]
                        )
            
            # Register RAG tools
            rag_tools = get_rag_tools()
            for tool_func in rag_tools:
                if tool_func.name not in self.tools:
                    self.tools[tool_func.name] = tool_func
                    if tool_func.name not in self.registry:
                        self.registry[tool_func.name] = ToolMetadata(
                            name=tool_func.name,
                            description=tool_func.description or "RAG/Knowledge tool",
                            category="rag",
                            author="langchain-agent-base",
                            version="1.0.0",
                            created_at=datetime.now().isoformat(),
                            source="base_rag_tools",
                            file_path=None,
                            dependencies=[],
                            tags=["predefined", "rag", "knowledge", "base_toolbox"]
                        )
            
        except ImportError as e:
            # Base toolboxes not available - that's ok for minimal installs
            pass
        except Exception as e:
            print(f"⚠️  Warning: Could not register predefined tools: {e}")
    
    def add_tool_from_code(self,
                          code: str,
                          category: str = "custom",
                          author: str = "unknown",
                          version: str = "1.0.0",
                          tags: List[str] = None,
                          force: bool = False) -> Tuple[bool, str, Optional[Callable]]:
        """
        Add a new tool from code string.
        
        Args:
            code: Python code for the tool (must include @tool decorator)
            category: Tool category (math, science, coding, business, custom, generated)
            author: Author name (e.g., "llm", "user", "agent")
            version: Version string
            tags: Optional tags for categorization
            force: Force overwrite if tool exists
        
        Returns:
            (success, message, tool_function)
        """
        # Validate code
        is_valid, message, tree = ToolValidator.validate_code(code)
        if not is_valid:
            return False, f"Validation failed: {message}", None
        
        # Extract tool info
        tool_info = ToolValidator.extract_tool_info(code, tree)
        tool_name = tool_info['name']
        
        if not tool_name:
            return False, "Could not extract tool name from code", None
        
        # Check for duplicates
        if tool_name in self.registry and not force:
            return False, f"Tool '{tool_name}' already exists. Use force=True to overwrite.", None
        
        # Calculate code hash for duplicate detection
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Check if identical code exists
        for existing_name, metadata in self.registry.items():
            if metadata.code_hash == code_hash and existing_name != tool_name:
                return False, f"Identical tool already exists as '{existing_name}'", None
        
        # Create metadata
        metadata = ToolMetadata(
            name=tool_name,
            description=tool_info['description'],
            category=category,
            author=author,
            version=version,
            function_signature=f"{tool_name}({', '.join(f'{k}: {v}' for k, v in tool_info['parameters'].items())})",
            code_hash=code_hash,
            parameters=tool_info['parameters'],
            tags=tags or [],
            dependencies=tool_info['dependencies']
        )
        
        # Ensure toolbox directories exist before writing any files
        self._ensure_dirs()
        
        # Determine file path
        file_name = f"{tool_name}.py"
        file_path = self.toolbox_dir / category / file_name
        metadata.file_path = str(file_path.relative_to(self.toolbox_dir))
        
        # Save code to file
        try:
            # Add header comment
            header = f'''"""
Tool: {tool_name}
Category: {category}
Author: {author}
Version: {version}
Created: {metadata.created_at}
Description: {tool_info['description'][:100]}...
"""

from langchain_core.tools import tool
{chr(10).join(f"import {dep}" for dep in tool_info['dependencies'] if dep != 'langchain_core.tools')}

'''
            full_code = header + code
            
            file_path.write_text(full_code, encoding='utf-8')
            
            # Execute code to get tool function
            namespace = {'tool': tool}
            exec(code, namespace)
            
            # Find the tool function
            tool_func = None
            for name, obj in namespace.items():
                if callable(obj) and hasattr(obj, 'name') and obj.name == tool_name:
                    tool_func = obj
                    break
            
            if tool_func is None:
                return False, "Could not extract tool function from code", None
            
            # Update registry
            self.registry[tool_name] = metadata
            self.tools[tool_name] = tool_func
            self._save_registry()
            
            return True, f"Tool '{tool_name}' added successfully to {category}", tool_func
            
        except Exception as e:
            return False, f"Error saving tool: {str(e)}\n{traceback.format_exc()}", None
    
    def add_tool_from_function(self,
                              tool_func: Callable,
                              category: str = "custom",
                              author: str = "user",
                              version: str = "1.0.0",
                              tags: List[str] = None) -> Tuple[bool, str]:
        """
        Add a tool from an existing function object.
        
        Args:
            tool_func: Function decorated with @tool
            category: Tool category
            author: Author name
            version: Version string
            tags: Optional tags
        
        Returns:
            (success, message)
        """
        if not hasattr(tool_func, 'name'):
            return False, "Function must be decorated with @tool"
        
        tool_name = tool_func.name
        
        # Get source code
        try:
            source_code = inspect.getsource(tool_func)
        except Exception:
            return False, "Could not extract source code from function"
        
        return self.add_tool_from_code(
            source_code,
            category=category,
            author=author,
            version=version,
            tags=tags
        )[:2]  # Return only success and message
    
    def get_tool(self, tool_name: str) -> Optional[Callable]:
        """Get a tool function by name."""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: str) -> List[Callable]:
        """Get all tools in a category."""
        tools = []
        for tool_name, metadata in self.registry.items():
            if metadata.category == category:
                tool_func = self.tools.get(tool_name)
                if tool_func:
                    tools.append(tool_func)
        return tools
    
    def get_tools_by_tags(self, tags: List[str]) -> List[Callable]:
        """Get tools matching any of the given tags."""
        tools = []
        for tool_name, metadata in self.registry.items():
            if any(tag in metadata.tags for tag in tags):
                tool_func = self.tools.get(tool_name)
                if tool_func:
                    tools.append(tool_func)
        return tools
    
    def get_tools_by_author(self, author: str) -> List[Callable]:
        """Get all tools by a specific author (e.g., 'llm', 'user')."""
        tools = []
        for tool_name, metadata in self.registry.items():
            if metadata.author == author:
                tool_func = self.tools.get(tool_name)
                if tool_func:
                    tools.append(tool_func)
        return tools
    
    def get_all_tools(self) -> List[Callable]:
        """Get all tools in the toolbox."""
        return list(self.tools.values())
    
    def list_tools(self, category: str = None, author: str = None) -> List[Dict[str, Any]]:
        """
        List all tools with metadata.
        
        Args:
            category: Filter by category
            author: Filter by author
        
        Returns:
            List of tool metadata dictionaries
        """
        tools = []
        for tool_name, metadata in self.registry.items():
            if category and metadata.category != category:
                continue
            if author and metadata.author != author:
                continue
            
            tools.append({
                'name': metadata.name,
                'description': metadata.description,
                'category': metadata.category,
                'author': metadata.author,
                'version': metadata.version,
                'parameters': metadata.parameters,
                'tags': metadata.tags,
                'created_at': metadata.created_at
            })
        
        return tools
    
    def remove_tool(self, tool_name: str) -> Tuple[bool, str]:
        """
        Remove a tool from the toolbox.
        
        Args:
            tool_name: Name of tool to remove
        
        Returns:
            (success, message)
        """
        if tool_name not in self.registry:
            return False, f"Tool '{tool_name}' not found"
        
        try:
            metadata = self.registry[tool_name]
            file_path = self.toolbox_dir / metadata.file_path
            
            # Remove file
            if file_path.exists():
                file_path.unlink()
            
            # Remove from registry and cache
            del self.registry[tool_name]
            if tool_name in self.tools:
                del self.tools[tool_name]
            
            self._save_registry()
            
            return True, f"Tool '{tool_name}' removed successfully"
            
        except Exception as e:
            return False, f"Error removing tool: {str(e)}"
    
    def test_tool(self, tool_name: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a tool with given test cases.
        
        Args:
            tool_name: Name of tool to test
            test_cases: List of test cases with 'input' and 'expected' keys
        
        Returns:
            Test results dictionary
        """
        if tool_name not in self.tools:
            return {'success': False, 'message': f"Tool '{tool_name}' not found"}
        
        tool_func = self.tools[tool_name]
        results = {
            'tool_name': tool_name,
            'total_tests': len(test_cases),
            'passed': 0,
            'failed': 0,
            'test_results': []
        }
        
        for i, test_case in enumerate(test_cases):
            test_input = test_case.get('input', {})
            expected = test_case.get('expected')
            
            try:
                # Invoke tool
                if hasattr(tool_func, 'invoke'):
                    result = tool_func.invoke(test_input)
                else:
                    result = tool_func(**test_input)
                
                # Check result
                passed = (expected is None) or (str(expected) in str(result))
                
                results['test_results'].append({
                    'test_number': i + 1,
                    'passed': passed,
                    'input': test_input,
                    'expected': expected,
                    'actual': result
                })
                
                if passed:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['test_results'].append({
                    'test_number': i + 1,
                    'passed': False,
                    'input': test_input,
                    'expected': expected,
                    'error': str(e)
                })
                results['failed'] += 1
        
        # Update metadata
        if tool_name in self.registry:
            self.registry[tool_name].tested = True
            self.registry[tool_name].test_results = results
            self._save_registry()
        
        return results
    
    def export_tools(self, output_file: str, category: str = None):
        """
        Export tools to a single Python file for easy distribution.
        
        Args:
            output_file: Path to output file
            category: Optional category filter
        """
        tools_to_export = []
        
        for tool_name, metadata in self.registry.items():
            if category and metadata.category != category:
                continue
            
            file_path = self.toolbox_dir / metadata.file_path
            if file_path.exists():
                tools_to_export.append((tool_name, file_path.read_text()))
        
        # Create export file
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('"""Exported Tools from Toolbox"""\n\n')
            f.write('from langchain_core.tools import tool\n\n')
            
            for tool_name, code in tools_to_export:
                f.write(f"# {tool_name}\n")
                f.write(code)
                f.write('\n\n')
            
            # Add collection function
            f.write('def get_exported_tools():\n')
            f.write('    """Get all exported tools."""\n')
            f.write('    return [\n')
            for tool_name, _ in tools_to_export:
                f.write(f'        {tool_name},\n')
            f.write('    ]\n')
        
        return f"Exported {len(tools_to_export)} tools to {output_path}"


# Global toolbox instance
_global_toolbox = None


def get_toolbox() -> ToolboxManager:
    """Get the global toolbox instance."""
    global _global_toolbox
    if _global_toolbox is None:
        _global_toolbox = ToolboxManager()
    return _global_toolbox


def create_tool_from_code(code: str, **kwargs) -> Tuple[bool, str, Optional[Callable]]:
    """
    Convenience function to create a tool from code using global toolbox.
    
    Args:
        code: Tool code with @tool decorator
        **kwargs: Additional arguments for add_tool_from_code
    
    Returns:
        (success, message, tool_function)
    """
    toolbox = get_toolbox()
    return toolbox.add_tool_from_code(code, **kwargs)


# Example usage and testing
if __name__ == "__main__":
    print("🧰 Testing Toolbox System")
    print("=" * 70)
    
    # Initialize toolbox
    toolbox = ToolboxManager(toolbox_dir="test_toolbox")
    
    # Example 1: Add tool from code
    print("\n1️⃣ Adding tool from code...")
    tool_code = '''
@tool
def factorial(n: int) -> str:
    """Calculate factorial of a number."""
    if n < 0:
        return "Error: n must be non-negative"
    result = 1
    for i in range(1, n + 1):
        result *= i
    return f"factorial({n}) = {result}"
'''
    
    success, message, func = toolbox.add_tool_from_code(
        tool_code,
        category="math",
        author="example",
        tags=["math", "factorial"]
    )
    print(f"   {message}")
    
    if success and func:
        # Test the tool
        print(f"   Testing: {func.invoke({'n': 5})}")
    
    # Example 2: List tools
    print("\n2️⃣ Listing tools...")
    tools = toolbox.list_tools()
    for tool_info in tools:
        print(f"   • {tool_info['name']} ({tool_info['category']}) - {tool_info['description'][:50]}...")
    
    # Example 3: Get tools by category
    print("\n3️⃣ Getting math tools...")
    math_tools = toolbox.get_tools_by_category("math")
    print(f"   Found {len(math_tools)} math tools")
    
    # Example 4: Test tool
    print("\n4️⃣ Testing tool...")
    test_results = toolbox.test_tool("factorial", [
        {'input': {'n': 5}, 'expected': '120'},
        {'input': {'n': 0}, 'expected': '1'},
        {'input': {'n': -1}, 'expected': 'Error'}
    ])
    print(f"   Tests: {test_results['passed']} passed, {test_results['failed']} failed")
    
    print("\n✅ Toolbox system test complete!")
