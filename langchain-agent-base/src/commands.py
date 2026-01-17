"""
Command System for Agents
=========================

A flexible command system that allows agents to have custom commands that can be
executed directly without going through the chat interface. Commands are like tools
but are meant to be called directly by the user rather than by the AI.

Usage:
    from src.commands import CommandRegistry, command
    from src.base import Agent
    
    # Create agent with command registry
    agent = Agent()
    agent.enable_commands()
    
    # Add custom command
    @command("hello")
    def say_hello(name: str = "World") -> str:
        return f"Hello, {name}!"
    
    agent.commands.add_command(say_hello)
    
    # Execute command directly
    result = agent.execute_command("/hello", name="Alice")
    print(result)  # "Hello, Alice!"
"""

import inspect
from typing import Dict, Callable, Any, Optional, List, get_type_hints
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class CommandInfo:
    """Information about a command."""
    name: str
    function: Callable
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    usage: str = ""


def command(name: str, description: str = None, usage: str = None):
    """
    Decorator to register a function as a command.
    
    Args:
        name: Command name (without /)
        description: Command description
        usage: Usage example
    """
    def decorator(func: Callable) -> Callable:
        # Store command metadata on the function
        func._command_name = name
        func._command_description = description or func.__doc__ or f"Execute {name} command"
        func._command_usage = usage or f"/{name}"
        
        # Extract parameter info from function signature
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        parameters = {}
        for param_name, param in sig.parameters.items():
            param_info = {
                'type': type_hints.get(param_name, str),
                'required': param.default == inspect.Parameter.empty,
                'default': param.default if param.default != inspect.Parameter.empty else None
            }
            parameters[param_name] = param_info
        
        func._command_parameters = parameters
        return func
    
    return decorator


class CommandRegistry:
    """
    Registry for managing agent commands.
    """
    
    def __init__(self):
        self.commands: Dict[str, CommandInfo] = {}
        self._add_built_in_commands()
    
    def _add_built_in_commands(self):
        """Add built-in utility commands."""
        
        @command("help", "Show available commands", "//help [command_name]")
        def help_command(command_name: str = None) -> str:
            if command_name:
                if command_name in self.commands:
                    cmd = self.commands[command_name]
                    result = f"**//{cmd.name}** - {cmd.description}\n"
                    if cmd.usage:
                        result += f"Usage: {cmd.usage}\n"
                    if cmd.parameters:
                        result += "Parameters:\n"
                        for param, info in cmd.parameters.items():
                            required = "required" if info['required'] else "optional"
                            default = f" (default: {info['default']})" if info['default'] is not None else ""
                            result += f"  - {param}: {info['type'].__name__} ({required}){default}\n"
                    return result
                else:
                    return f"Command '{command_name}' not found."
            
            result = "Available Commands:\n"
            for name, cmd in self.commands.items():
                result += f"  //{name} - {cmd.description}\n"
            result += "\nUse //help <command_name> for detailed help on a specific command."
            return result
        
        @command("list", "List all available commands")
        def list_commands() -> str:
            if not self.commands:
                return "No commands available."
            
            result = "Available Commands:\n"
            for name in sorted(self.commands.keys()):
                result += f"  //{name}\n"
            return result
        
        # Add built-in commands to registry
        self.add_command(help_command)
        self.add_command(list_commands)
    
    def add_command(self, func: Callable) -> None:
        if not hasattr(func, '_command_name'):
            raise ValueError("Function must be decorated with @command")
        
        command_info = CommandInfo(
            name=func._command_name,
            function=func,
            description=func._command_description,
            parameters=func._command_parameters,
            usage=func._command_usage
        )
        
        self.commands[func._command_name] = command_info
    
    def remove_command(self, name: str) -> bool:
        """
        Remove a command from the registry.
        
        Args:
            name: Command name
            
        Returns:
            True if command was removed, False if not found
        """
        if name in self.commands:
            del self.commands[name]
            return True
        return False
    
    def execute_command(self, command_str: str, **kwargs) -> str:
        """
        Execute a command by name.
        
        Args:
            command_str: Command string (with or without /)
            **kwargs: Command arguments
            
        Returns:
            Command result as string
        """
        # Remove leading / if present
        command_name = command_str.lstrip('/')
        
        if command_name not in self.commands:
            available = ', '.join(self.commands.keys())
            return f"Command '{command_name}' not found. Available commands: {available}"
        
        command_info = self.commands[command_name]
        
        try:
            # Validate and prepare arguments
            prepared_kwargs = self._prepare_arguments(command_info, kwargs)
            
            # Execute the command
            result = command_info.function(**prepared_kwargs)
            
            return str(result) if result is not None else "Command executed successfully."
            
        except Exception as e:
            return f"Error executing command '{command_name}': {str(e)}"
    
    def _prepare_arguments(self, command_info: CommandInfo, provided_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare and validate command arguments.
        
        Args:
            command_info: Command information
            provided_kwargs: User-provided arguments
            
        Returns:
            Prepared arguments dictionary
        """
        prepared = {}
        
        for param_name, param_info in command_info.parameters.items():
            if param_name in provided_kwargs:
                # Use provided value
                value = provided_kwargs[param_name]
                # TODO: Add type conversion/validation here if needed
                prepared[param_name] = value
            elif param_info['required']:
                # Required parameter missing
                raise ValueError(f"Required parameter '{param_name}' not provided")
            elif param_info['default'] is not None:
                # Use default value
                prepared[param_name] = param_info['default']
        
        return prepared
    
    def get_command_info(self, name: str) -> Optional[CommandInfo]:
        """Get information about a command."""
        return self.commands.get(name)
    
    def list_command_names(self) -> List[str]:
        """Get list of all command names."""
        return list(self.commands.keys())


# Convenience functions for common command patterns
def create_math_commands() -> List[Callable]:
    """Create math-related commands."""
    
    @command("calc", "Quick calculation", "//calc <expression>")
    def quick_calc(expression: str) -> str:
        """Quick mathematical calculation."""
        try:
            # Import here to avoid dependency issues
            from src.tools import advanced_calculator
            # Properly invoke the LangChain tool
            result = advanced_calculator.invoke({"expression": expression})
            return result
        except Exception as e:
            return f"Calculation error: {e}"
    
    @command("solve", "Solve quadratic equation", "//solve <a> <b> <c>")
    def solve_quadratic_cmd(a: float, b: float, c: float) -> str:
        """Solve quadratic equation ax² + bx + c = 0."""
        try:
            from src.tools import solve_quadratic
            # Properly invoke the LangChain tool
            result = solve_quadratic.invoke({"a": a, "b": b, "c": c})
            return result
        except Exception as e:
            return f"Solve error: {e}"
    
    return [quick_calc, solve_quadratic_cmd]


def create_science_commands() -> List[Callable]:
    """Create science-related commands."""
    
    @command("convert", "Convert units", "//convert <value> <from_unit> <to_unit>")
    def unit_convert_cmd(value: float, from_unit: str, to_unit: str) -> str:
        """Convert between units."""
        try:
            from src.tools import unit_converter
            # Properly invoke the LangChain tool
            result = unit_converter.invoke({
                "value": value, 
                "from_unit": from_unit, 
                "to_unit": to_unit
            })
            return result
        except Exception as e:
            return f"Conversion error: {e}"
    
    @command("physics", "Physics calculation", "//physics <formula> [parameters...]")
    def physics_cmd(formula: str, **kwargs) -> str:
        """Perform physics calculations."""
        try:
            from src.tools import physics_calculator
            # Properly invoke the LangChain tool
            result = physics_calculator.invoke({
                "calculation": formula, 
                **kwargs
            })
            return result
        except Exception as e:
            return f"Physics error: {e}"
    
    return [unit_convert_cmd, physics_cmd]


def create_coding_commands() -> List[Callable]:
    """Create coding-related commands."""
    
    @command("analyze", "Analyze code", "/analyze <code> [language]")
    def analyze_code_cmd(code: str, language: str = "python") -> str:
        """Analyze code structure and quality."""
        try:
            from src.tools import code_analyzer
            # Properly invoke the LangChain tool
            result = code_analyzer.invoke({
                "code": code, 
                "language": language
            })
            return result
        except Exception as e:
            return f"Analysis error: {e}"
    
    @command("format", "Format JSON", "//format <json_string>")
    def format_json_cmd(json_string: str) -> str:
        """Format and validate JSON."""
        try:
            from src.tools import json_formatter
            # Properly invoke the LangChain tool
            result = json_formatter.invoke({
                "json_string": json_string, 
                "operation": "format"
            })
            return result
        except Exception as e:
            return f"Format error: {e}"
    
    return [analyze_code_cmd, format_json_cmd]


def create_agent_commands() -> List[Callable]:
    """
    Create agent management commands.
    
    Note: Shell commands (pwd, cd, shell execution) are provided by base coding tools.
    This keeps commands minimal and avoids duplication.
    """
    
    @command("status", "Show agent status")
    def agent_status() -> str:
        """Show current agent status and capabilities."""
        return "✅ Agent is running and ready."
    
    return [agent_status]