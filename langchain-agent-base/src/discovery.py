"""
Dynamic Tool and Command Discovery System
=========================================

Automatically discovers, registers, and generates API endpoints for
new tools and commands as they are added to the system.

NOTE: This module is designed for the optional FastAPI protocol server.
For basic agent usage, you don't need discovery - use ToolboxManager instead:
    
    from toolbox import get_toolbox
    toolbox = get_toolbox()
    tools = toolbox.get_tools_by_category("coding")
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Any, Type, Callable, Set
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .protocol import get_agent_registry, AgentCard
from .commands import CommandRegistry


@dataclass
class ToolInfo:
    """Information about a discovered tool."""
    name: str
    function: Callable
    description: str
    module_path: str
    category: str
    parameters: Dict[str, Any]


@dataclass
class CommandInfo:
    """Information about a discovered command.""" 
    name: str
    function: Callable
    description: str
    usage: str
    module_path: str
    parameters: Dict[str, Any]


class DiscoveryEngine:
    """
    Engine for discovering and registering tools, commands, and agents.
    """
    
    def __init__(self):
        self.discovered_tools: Dict[str, ToolInfo] = {}
        self.discovered_commands: Dict[str, CommandInfo] = {}
        self.discovered_agents: Dict[str, Type] = {}
        self.watched_directories: Set[str] = set()
        
    def add_watch_directory(self, directory: str):
        """Add directory to watch for new tools and commands."""
        path = Path(directory).resolve()
        if path.exists() and path.is_dir():
            self.watched_directories.add(str(path))
            print(f"👀 Watching directory: {directory}")
        else:
            print(f"⚠️ Directory not found: {directory}")
    
    def discover_tools(self, module_path: str = None) -> List[ToolInfo]:
        """
        Discover all tools in a module or directory.
        
        Args:
            module_path: Specific module to scan, or None for all watched directories
            
        Returns:
            List of discovered tools
        """
        tools = []
        
        if module_path:
            tools.extend(self._scan_module_for_tools(module_path))
        else:
            # Scan all watched directories
            for directory in self.watched_directories:
                tools.extend(self._scan_directory_for_tools(directory))
            
            # Also scan built-in tools
            tools.extend(self._scan_builtin_tools())
        
        # Update discovered tools registry
        for tool in tools:
            self.discovered_tools[tool.name] = tool
            
        return tools
    
    def discover_commands(self, module_path: str = None) -> List[CommandInfo]:
        """
        Discover all commands in a module or directory.
        
        Args:
            module_path: Specific module to scan, or None for all watched directories
            
        Returns:
            List of discovered commands
        """
        commands = []
        
        if module_path:
            commands.extend(self._scan_module_for_commands(module_path))
        else:
            # Scan all watched directories  
            for directory in self.watched_directories:
                commands.extend(self._scan_directory_for_commands(directory))
                
            # Also scan built-in commands
            commands.extend(self._scan_builtin_commands())
        
        # Update discovered commands registry
        for command in commands:
            self.discovered_commands[command.name] = command
            
        return commands
    
    def discover_agents(self, module_path: str = None) -> List[Type]:
        """
        Discover all agent classes in a module or directory.
        
        Args:
            module_path: Specific module to scan, or None for all watched directories
            
        Returns:
            List of discovered agent classes
        """
        agents = []
        
        if module_path:
            agents.extend(self._scan_module_for_agents(module_path))
        else:
            # Scan all watched directories
            for directory in self.watched_directories:
                agents.extend(self._scan_directory_for_agents(directory))
        
        # Update discovered agents registry
        for agent_class in agents:
            self.discovered_agents[agent_class.__name__] = agent_class
            
        return agents
    
    def _scan_builtin_tools(self) -> List[ToolInfo]:
        """Scan built-in tools from base toolbox modules."""
        tools = []
        
        try:
            # Import toolbox manager to get tools from base toolboxes
            from .toolbox import get_toolbox
            
            toolbox = get_toolbox()
            all_categories = toolbox.categories  # Use the categories list
            
            for category in all_categories:
                category_tools = toolbox.get_tools_by_category(category)
                
                for tool in category_tools:
                    if hasattr(tool, 'name') and hasattr(tool, 'description'):
                        tool_info = ToolInfo(
                            name=tool.name,
                            function=tool,
                            description=tool.description,
                            module_path=f"src.base_{category}_tools",
                            category=category,  # Use actual category instead of guessing
                            parameters=self._extract_tool_parameters(tool)
                        )
                        tools.append(tool_info)
                    
        except Exception as e:
            print(f"⚠️ Error scanning built-in tools: {e}")
            
        return tools
    
    def _scan_builtin_commands(self) -> List[CommandInfo]:
        """Scan built-in commands from .commands module."""
        commands = []
        
        try:
            from .commands import (
                create_math_commands, 
                create_science_commands, 
                create_coding_commands,
                create_agent_commands  # Added - was missing
            )
            
            # Get command collections
            command_collections = [
                ("math", create_math_commands()),
                ("science", create_science_commands()), 
                ("coding", create_coding_commands()),
                ("agent", create_agent_commands())  # Added - was missing
            ]
            
            for category, command_funcs in command_collections:
                for func in command_funcs:
                    if hasattr(func, '_command_name'):
                        command_info = CommandInfo(
                            name=func._command_name,
                            function=func,
                            description=func._command_description,
                            usage=func._command_usage,
                            module_path=f"src.commands.{category}",
                            parameters=getattr(func, '_command_parameters', {})
                        )
                        commands.append(command_info)
                        
        except Exception as e:
            print(f"⚠️ Error scanning built-in commands: {e}")
            
        return commands
    
    def _scan_directory_for_tools(self, directory: str) -> List[ToolInfo]:
        """Scan directory for Python files containing tools."""
        tools = []
        
        try:
            for file_path in Path(directory).rglob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                    
                module_name = self._file_to_module_name(file_path, directory)
                tools.extend(self._scan_module_for_tools(module_name))
                
        except Exception as e:
            print(f"⚠️ Error scanning directory {directory}: {e}")
            
        return tools
    
    def _scan_directory_for_commands(self, directory: str) -> List[CommandInfo]:
        """Scan directory for Python files containing commands."""
        commands = []
        
        try:
            for file_path in Path(directory).rglob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                    
                module_name = self._file_to_module_name(file_path, directory)
                commands.extend(self._scan_module_for_commands(module_name))
                
        except Exception as e:
            print(f"⚠️ Error scanning directory {directory}: {e}")
            
        return commands
    
    def _scan_directory_for_agents(self, directory: str) -> List[Type]:
        """Scan directory for Python files containing agent classes."""
        agents = []
        
        try:
            for file_path in Path(directory).rglob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                    
                module_name = self._file_to_module_name(file_path, directory)
                agents.extend(self._scan_module_for_agents(module_name))
                
        except Exception as e:
            print(f"⚠️ Error scanning directory {directory}: {e}")
            
        return agents
    
    def _scan_module_for_tools(self, module_name: str) -> List[ToolInfo]:
        """Scan specific module for tool functions."""
        tools = []
        
        try:
            module = importlib.import_module(module_name)
            
            for name in dir(module):
                obj = getattr(module, name)
                
                # Check if it's a LangChain tool
                if (hasattr(obj, 'name') and 
                    hasattr(obj, 'description') and
                    callable(obj)):
                    
                    tool_info = ToolInfo(
                        name=obj.name,
                        function=obj,
                        description=obj.description,
                        module_path=module_name,
                        category=self._categorize_tool(obj.name),
                        parameters=self._extract_tool_parameters(obj)
                    )
                    tools.append(tool_info)
                    
        except Exception as e:
            print(f"⚠️ Error scanning module {module_name}: {e}")
            
        return tools
    
    def _scan_module_for_commands(self, module_name: str) -> List[CommandInfo]:
        """Scan specific module for command functions."""
        commands = []
        
        try:
            module = importlib.import_module(module_name)
            
            for name in dir(module):
                obj = getattr(module, name)
                
                # Check if it's a command function
                if (hasattr(obj, '_command_name') and 
                    hasattr(obj, '_command_description') and
                    callable(obj)):
                    
                    command_info = CommandInfo(
                        name=obj._command_name,
                        function=obj,
                        description=obj._command_description,
                        usage=getattr(obj, '_command_usage', f"/{obj._command_name}"),
                        module_path=module_name,
                        parameters=getattr(obj, '_command_parameters', {})
                    )
                    commands.append(command_info)
                    
        except Exception as e:
            print(f"⚠️ Error scanning module {module_name}: {e}")
            
        return commands
    
    def _scan_module_for_agents(self, module_name: str) -> List[Type]:
        """Scan specific module for agent classes.""" 
        agents = []
        
        try:
            module = importlib.import_module(module_name)
            
            for name in dir(module):
                obj = getattr(module, name)
                
                # Check if it's an agent class
                if (inspect.isclass(obj) and 
                    hasattr(obj, 'chat') and
                    hasattr(obj, 'tools')):
                    
                    agents.append(obj)
                    
        except Exception as e:
            print(f"⚠️ Error scanning module {module_name}: {e}")
            
        return agents
    
    def _file_to_module_name(self, file_path: Path, base_directory: str) -> str:
        """Convert file path to module name."""
        relative_path = file_path.relative_to(base_directory)
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        return ".".join(module_parts)
    
    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize tool based on name patterns."""
        name_lower = tool_name.lower()
        
        if any(word in name_lower for word in ['calc', 'math', 'equation', 'solve', 'matrix']):
            return "math"
        elif any(word in name_lower for word in ['unit', 'physics', 'chemistry', 'convert']):
            return "science"
        elif any(word in name_lower for word in ['code', 'regex', 'json', 'analyze']):
            return "coding"
        elif any(word in name_lower for word in ['search', 'rag', 'document', 'retriev']):
            return "rag"
        elif any(word in name_lower for word in ['weather', 'api', 'web']):
            return "api"
        else:
            return "custom"
    
    def _extract_tool_parameters(self, tool_func) -> Dict[str, Any]:
        """Extract parameter information from tool function."""
        try:
            signature = inspect.signature(tool_func.func if hasattr(tool_func, 'func') else tool_func)
            parameters = {}
            
            for param_name, param in signature.parameters.items():
                param_info = {
                    'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
                    'required': param.default == inspect.Parameter.empty,
                    'default': param.default if param.default != inspect.Parameter.empty else None
                }
                parameters[param_name] = param_info
                
            return parameters
            
        except Exception:
            return {}
    
    def get_tool_by_category(self, category: str) -> List[ToolInfo]:
        """Get all tools in a specific category."""
        return [tool for tool in self.discovered_tools.values() if tool.category == category]
    
    def get_available_categories(self) -> List[str]:
        """Get all available tool categories."""
        return list(set(tool.category for tool in self.discovered_tools.values()))


class AutoRegisterMixin:
    """
    Mixin class for automatic registration of agents with the protocol.
    """
    
    @classmethod
    def auto_register(cls, 
                     name: str = None,
                     version: str = "1.0.0",
                     domain: str = "general",
                     **kwargs):
        """
        Automatically register this agent class with the protocol.
        
        Args:
            name: Agent name (defaults to class name)
            version: Version string
            domain: Agent domain
            **kwargs: Additional registration parameters
        """
        from .protocol import register_agent
        
        agent_name = name or cls.__name__.lower().replace('agent', '')
        
        # Register with decorator
        register_agent(
            name=agent_name,
            version=version,
            domain=domain,
            **kwargs
        )(cls)
        
        print(f"🤖 Auto-registered agent: {agent_name} v{version}")


class ProtocolWatcher:
    """
    File system watcher for automatic discovery of new agents, tools, and commands.
    """
    
    def __init__(self, discovery_engine: DiscoveryEngine):
        self.discovery_engine = discovery_engine
        self.last_scan_times: Dict[str, float] = {}
    
    def scan_for_changes(self):
        """Scan watched directories for changes and update registry."""
        try:
            import time
            current_time = time.time()
            
            for directory in self.discovery_engine.watched_directories:
                last_scan = self.last_scan_times.get(directory, 0)
                
                # Check if any files have been modified
                needs_rescan = False
                for file_path in Path(directory).rglob("*.py"):
                    if file_path.stat().st_mtime > last_scan:
                        needs_rescan = True
                        break
                
                if needs_rescan:
                    print(f"🔄 Rescanning directory: {directory}")
                    
                    # Rediscover tools and commands
                    new_tools = self.discovery_engine.discover_tools()
                    new_commands = self.discovery_engine.discover_commands()
                    new_agents = self.discovery_engine.discover_agents()
                    
                    print(f"   Found: {len(new_tools)} tools, {len(new_commands)} commands, {len(new_agents)} agents")
                    
                    # Update last scan time
                    self.last_scan_times[directory] = current_time
                    
        except Exception as e:
            print(f"⚠️ Error during file system scan: {e}")


# Global discovery engine
_global_discovery_engine = None


def get_discovery_engine() -> DiscoveryEngine:
    """Get global discovery engine."""
    global _global_discovery_engine
    if _global_discovery_engine is None:
        _global_discovery_engine = DiscoveryEngine()
    return _global_discovery_engine


def auto_discover_all(watch_directories: List[str] = None):
    """
    Automatically discover all tools, commands, and agents.
    
    Args:
        watch_directories: Directories to watch for new code
    """
    engine = get_discovery_engine()
    
    # Add watch directories
    if watch_directories:
        for directory in watch_directories:
            engine.add_watch_directory(directory)
    
    # Discover everything
    tools = engine.discover_tools()
    commands = engine.discover_commands() 
    agents = engine.discover_agents()
    
    print(f"🔍 Discovery complete:")
    print(f"   📋 Tools: {len(tools)}")
    print(f"   ⚡ Commands: {len(commands)}")
    print(f"   🤖 Agents: {len(agents)}")
    
    return {
        "tools": tools,
        "commands": commands,
        "agents": agents
    }


def start_protocol_watcher(watch_directories: List[str] = None, scan_interval: int = 30):
    """
    Start file system watcher for automatic discovery.
    
    Args:
        watch_directories: Directories to watch
        scan_interval: Scan interval in seconds
    """
    import threading
    import time
    
    engine = get_discovery_engine()
    
    if watch_directories:
        for directory in watch_directories:
            engine.add_watch_directory(directory)
    
    watcher = ProtocolWatcher(engine)
    
    def watch_loop():
        while True:
            watcher.scan_for_changes()
            time.sleep(scan_interval)
    
    # Start watcher in background thread
    watcher_thread = threading.Thread(target=watch_loop, daemon=True)
    watcher_thread.start()
    
    print(f"👀 Started protocol watcher (scan interval: {scan_interval}s)")
