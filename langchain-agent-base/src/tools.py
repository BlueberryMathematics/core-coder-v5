"""
Tool Collection Manager
========================

Central registry for all tool collections.
Imports from base toolbox modules and provides unified access.

Base Toolboxes:
- base_coding_tools: File operations, code analysis, project management
- base_math_tools: Calculators, equations, matrices
- base_science_tools: Unit conversion, physics, chemistry
- base_rag_tools: Knowledge base, documentation search, memory

Usage:
    from tools import get_coding_tools, get_math_tools, get_all_tools
    
    # Get specific toolbox
    coding_tools = get_coding_tools()
    
    # Get all tools
    all_tools = get_all_tools()
"""

from langchain_core.tools import tool

# Import all base toolboxes
from base_coding_tools import (
    code_analyzer, syntax_checker, regex_helper, json_formatter,
    read_file_content, write_file_content, get_file_tree, 
    list_directory_contents, search_files, search_in_files,
    get_file_info, create_project_structure, git_helper,
    get_python_info,  # Terminal commands provided by ShellToolMiddleware
    propose_file_create, propose_file_edit, propose_file_delete
)

from base_math_tools import (
    advanced_calculator, solve_quadratic, matrix_operations
)

from base_science_tools import (
    unit_converter, chemistry_helper, physics_calculator
)

from base_rag_tools import (
    search_knowledge_base, ingest_reference_file, 
    get_conversation_summary, search_documentation
)


# ============================================================================
# BASIC TOOLS (General Purpose - Legacy/Example)
# ============================================================================

@tool
def get_weather(location: str) -> str:
    """Get weather for a location (placeholder)."""
    return f"Weather in {location}: Sunny, 72°F (placeholder)"


@tool
def magic_calculator(a: int, b: int) -> int:
    """Simple calculator that adds two numbers."""
    return a + b


# ============================================================================
# TOOL COLLECTION FUNCTIONS
# ============================================================================

def get_basic_tools():
    """
    Get basic general-purpose tools.
    
    Returns:
        List of basic tools (weather, simple calculator)
    """
    return [
        get_weather,
        magic_calculator,
    ]


def get_math_tools():
    """
    Get mathematical computation tools.
    
    Returns:
        List of math tools (calculator, equations, matrices)
    """
    return [
        advanced_calculator,
        solve_quadratic,
        matrix_operations,
    ]


def get_science_tools():
    """
    Get scientific calculation tools.
    
    Returns:
        List of science tools (unit conversion, chemistry, physics)
    """
    return [
        unit_converter,
        chemistry_helper,
        physics_calculator,
    ]


def get_coding_tools():
    """
    Get comprehensive software development tools.
    
    Returns:
        List of coding tools (20 tools total):
        - File operations: read, write, tree, info
        - Directory: list, search in files, search files
        - Code analysis: analyzer, syntax checker, regex, JSON formatter
        - Project: create structure, git helper
        - Dev utils: Python info
        - Proposals: propose create/edit/delete files
        
    Note: Shell execution provided by ShellToolMiddleware when enable_shell_tool=True
    """
    return [
        # File operations
        read_file_content,
        write_file_content,
        get_file_tree,
        get_file_info,
        
        # Directory operations
        list_directory_contents,
        search_files,
        search_in_files,
        
        # Code analysis
        code_analyzer,
        syntax_checker,
        regex_helper,
        json_formatter,
        
        # Project management
        create_project_structure,
        git_helper,
        
        # Development utilities
        get_python_info,
        # Shell commands: Use enable_shell_tool=True in agent config
        
        # File proposals (human-in-loop)
        propose_file_create,
        propose_file_edit,
        propose_file_delete,
    ]


def get_rag_tools():
    """
    Get RAG/knowledge base tools separately.
    
    Returns:
        List of RAG tools (knowledge search, file ingestion, memory)
    """
    return [
        search_knowledge_base,
        ingest_reference_file,
        get_conversation_summary,
        search_documentation,
    ]


def get_all_tools():
    """
    Get all available tools from all categories.
    
    Returns:
        List of all tools combined
    """
    return (
        get_basic_tools() +
        get_math_tools() +
        get_science_tools() +
        get_coding_tools()
    )


# ============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ============================================================================
# For exports and old code that use previous function names

# Legacy function name
get_tools = get_all_tools

# Legacy tool name aliases (exports may use old names)
read_file = read_file_content
write_file = write_file_content
list_directory = list_directory_contents
