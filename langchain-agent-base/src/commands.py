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
import os
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


def create_cli_agent_commands(agent_instance, cli_instance, agent_config: dict, simple_memory, save_config_fn: Callable) -> List[Callable]:
    """
    Create CLI-specific agent commands with access to runtime instances.
    These are the //commands used in the interactive CLI.
    
    Args:
        agent_instance: The agent instance (for list_tools, etc.)
        cli_instance: The CLI instance (for enable_memory, session_id, etc.)
        agent_config: The AGENT_CONFIG dictionary
        simple_memory: The SimpleConversationMemory instance
        save_config_fn: Function to save config changes
    
    Returns:
        List of command functions ready to be registered
    """
    
    # Help command - formatted like the old version
    @command("help", "Show help information", "//help [command_name]")
    def show_help(command_name: str = None) -> str:
        """Show formatted help information."""
        if command_name:
            # Show help for specific command (use the registry's built-in logic)
            # This will be handled by the registry but we need to implement it here
            return f"Help for specific commands: Use //list to see all commands"
        
        # Full formatted help display (matching old design exactly)
        result = "\n" + "="*70 + "\n"
        result += f"  {agent_config.get('name', 'Agent')} - Help\n"
        result += "="*70 + "\n\n"
        
        result += "Basic Commands:\n"
        result += "  exit, quit, q  - Exit the CLI\n"
        result += "  clear          - Clear the screen\n"
        result += "  help           - Show this help message\n\n"
        
        result += "Special Commands (// prefix):\n"
        result += "  //tools        - List all available tools\n"
        result += "  //system_prompt [new_prompt_optional] - Show or set the system prompt\n"
        result += "  //status       - Show agent status and configuration\n"
        result += "  //config       - Show full configuration\n"
        result += "  //ollama list  - List available Ollama models\n"
        result += "  //groq list    - List available Groq models\n"
        result += "  //model <provider> <name> - Switch provider and model\n"
        result += "  //memory status|clear|show - Manage conversation memory\n"
        result += "  //rag status|search <query> - RAG knowledge base\n"
        result += "  //clear        - Clear the screen\n"
        result += "  //help         - Show this help\n\n"
        
        result += "Agent Features:\n"
        result += f"  - Provider: {agent_config.get('provider', 'unknown')}\n"
        result += f"  - Model: {agent_config.get('model_name', 'unknown')}\n"
        result += f"  - Temperature: {agent_config.get('temperature', 0.0)}\n"
        result += f"  - Memory: {'Enabled' if cli_instance.enable_memory else 'Disabled'}\n"
        
        # Show message count if memory is enabled
        if simple_memory and cli_instance.enable_memory:
            history = simple_memory.get_history(cli_instance.session_id)
            if history:
                result += f"    └─ Messages in context: {len(history)}\n"
        
        result += f"  - RAG: {'Enabled' if agent_config.get('enable_rag') else 'Disabled'}\n"
        
        # Show tool count
        try:
            tool_count = len(agent_instance.tools) if hasattr(agent_instance, 'tools') else 0
            result += f"  - Tools: {tool_count} available\n"
        except:
            result += "  - Tools: Available\n"
        
        result += "\n" + "="*70
        return result
    
    # Tools command
    @command("tools", "List all available tools")
    def list_tools() -> str:
        try:
            tools = agent_instance.list_tools()
            if tools:
                result = "\n╔════════════════════════════════════════════════════════════╗\n"
                result += "║                    🛠️  Available Tools                    ║\n"
                result += "╚════════════════════════════════════════════════════════════╝\n\n"
                for i, tool_name in enumerate(tools, 1):
                    result += f"{i:4}. {tool_name}\n"
                result += f"\nTotal: {len(tools)} tools loaded"
                return result
            else:
                return "No tools currently loaded"
        except Exception as e:
            return f"Unable to list tools: {e}"
    
    # System Prompt command
    @command("system_prompt", "Show or set the system prompt", "//system_prompt [new_prompt]")
    def system_prompt_cmd(new_prompt: str = None) -> str:
        if new_prompt:
            agent_config['system_prompt'] = new_prompt
            save_config_fn()
            cli_instance.reinitialize_model()  # Rebuild agent with new prompt
            return f"✓ System prompt updated and agent reinitialized"
        else:
            # Show the full assembled system prompt (all parts like in UI)
            result = "\n╔════════════════════════════════════════════════════════════╗\n"
            result += "║              📋 Agent System Prompt (Full)                ║\n"
            result += "╚════════════════════════════════════════════════════════════╝\n\n"
            
            # Show all parts that get assembled into the actual prompt
            if agent_config.get('prompt_opening'):
                result += "═══ Opening (before your prompt) ═══\n"
                result += agent_config['prompt_opening'].replace('{agentName}', agent_config.get('name', 'Agent'))
                result += "\n\n"
            
            result += "═══ Your Core Instructions ═══\n"
            result += agent_config.get('system_prompt', 'Not set')
            result += "\n\n"
            
            if agent_config.get('enable_shell', True) and agent_config.get('prompt_shell'):
                result += "═══ Shell Instructions (when enabled) ═══\n"
                result += agent_config['prompt_shell']
                result += "\n\n"
            
            if agent_config.get('prompt_closing'):
                result += "═══ Closing ═══\n"
                result += agent_config['prompt_closing']
                result += "\n\n"
            
            result += "Note: System context (OS, Shell, Python info) is added automatically at startup."
            
            return result
    
    # Status command
    @command("status", "Show agent status and configuration")
    def show_status() -> str:
        result = "\n╔════════════════════════════════════════════════════════════╗\n"
        result += "║                    Agent Status                            ║\n"
        result += "╚════════════════════════════════════════════════════════════╝\n\n"
        result += f"Name:        {agent_config.get('name', 'Agent')}\n"
        result += f"Provider:    {agent_config.get('provider', 'unknown')}\n"
        result += f"Model:       {agent_config.get('model_name', 'unknown')}\n"
        result += f"Temperature: {agent_config.get('temperature', 0.0)}\n"
        result += f"Memory:      {'Enabled' if cli_instance.enable_memory else 'Disabled'}\n"
        result += f"RAG:         {'Enabled' if agent_config.get('enable_rag') else 'Disabled'}\n"
        result += f"Session:     {cli_instance.session_id}\n"
        result += f"Messages in context: {len(simple_memory.get_history(cli_instance.session_id)) if simple_memory and cli_instance.enable_memory else 0}\n"
        result += f"Current working directory: {os.getcwd()}\n"
        return result
    
    # Model command
    @command("model", "Switch model and provider", "//model <provider> <model_name>")
    def switch_model(provider: str = None, model: str = None) -> str:
        if not provider or not model:
            return f"""Current provider: {agent_config.get('provider', 'unknown')}
Current model: {agent_config.get('model_name', 'unknown')}

Usage: //model <provider> <model_name>
Example: //model ollama qwen3:4b
Example: //model groq llama-3.3-70b-versatile

Use //groq list or //ollama list to see available models"""
        
        if provider.lower() not in ['groq', 'ollama']:
            return f"Invalid provider: {provider}. Available: groq, ollama"
        
        agent_config['provider'] = provider.lower()
        agent_config['model_name'] = model
        save_config_fn()
        cli_instance.reinitialize_model()
        return f"✓ Switched to {provider} / {model}"
    
    # Memory commands
    @command("memory", "Manage conversation memory", "//memory <status|clear|show>")
    def memory_cmd(action: str = "status") -> str:
        if action == "status":
            result = "\nMemory Status:\n"
            result += f"  Enabled: {cli_instance.enable_memory}\n"
            if simple_memory:
                history = simple_memory.get_history(cli_instance.session_id)
                result += f"  Messages: {len(history)}\n"
            return result
        elif action == "clear":
            if simple_memory:
                simple_memory.clear(cli_instance.session_id)
                return "✓ Memory cleared"
            return "Memory not available"
        elif action == "show":
            if simple_memory:
                history = simple_memory.get_history(cli_instance.session_id)
                if history:
                    result = f"\nConversation History ({len(history)} messages):\n"
                    for i, msg in enumerate(history[-5:], 1):
                        result += f"  {i}. You: {msg['message'][:50]}...\n"
                        result += f"     Agent: {msg['response'][:50]}...\n"
                    return result
                return "No conversation history"
            return "Memory not available"
        return f"Unknown memory action: {action}"
    
    # Ollama command
    @command("ollama", "Manage Ollama models", "//ollama <list|info>")
    def ollama_cmd(action: str = "list") -> str:
        if action == "list":
            try:
                import subprocess
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return "\nAvailable Ollama Models:\n" + result.stdout
                return f"Error listing Ollama models: {result.stderr}"
            except FileNotFoundError:
                return "Ollama is not installed or not in PATH"
            except Exception as e:
                return f"Error: {e}"
        return f"Unknown ollama action: {action}"
    
    # Groq command
    @command("groq", "Manage Groq models", "//groq list")
    def groq_cmd(action: str = "list") -> str:
        if action == "list":
            result = "\nAvailable Groq Models:\n"
            result += "  • llama-3.3-70b-versatile\n"
            result += "  • llama-3.1-70b-versatile\n"
            result += "  • mixtral-8x7b-32768\n"
            result += "  • gemma2-9b-it\n"
            result += "\nUse: //model groq <model_name>"
            return result
        return f"Unknown groq action: {action}"
    
    # RAG command
    @command("rag", "Manage RAG knowledge base", "//rag <status|search> [query]")
    def rag_cmd(action: str = "status", query: str = None) -> str:
        if action == "status":
            rag_enabled = agent_config.get('enable_rag', False)
            result = "\nRAG Status:\n"
            result += f"  Enabled: {rag_enabled}\n"
            if rag_enabled:
                result += "  Knowledge base: Active\n"
            else:
                result += "  To enable: Set enable_rag: true in config"
            return result
        elif action == "search":
            if not query:
                return "Usage: //rag search <query>"
            # TODO: Implement RAG search when RAG is fully integrated
            return f"RAG search for: {query}\n(RAG search not yet implemented)"
        return f"Unknown rag action: {action}"
    
    # Clear command
    @command("clear", "Clear the screen")
    def clear_screen() -> str:
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        return ""
    
    # Config command
    @command("config", "Show full configuration")
    def show_config() -> str:
        result = "\n╔════════════════════════════════════════════════════════════╗\n"
        result += "║                  ⚙️  Agent Configuration                   ║\n"
        result += "╚════════════════════════════════════════════════════════════╝\n\n"
        result += "Core Settings:\n"
        result += f"  Name:        {agent_config.get('name', 'N/A')}\n"
        result += f"  Provider:    {agent_config.get('provider', 'unknown')}\n"
        result += f"  Model:       {agent_config.get('model_name', 'unknown')}\n"
        result += f"  Temperature: {agent_config.get('temperature', 0.0)}\n\n"
        result += "Features:\n"
        result += f"  Memory: {'✓ Enabled' if agent_config.get('enable_memory') else '✗ Disabled'}\n"
        result += f"  RAG:    {'✓ Enabled' if agent_config.get('enable_rag') else '✗ Disabled'}\n"
        result += f"  Shell:  {'✓ Enabled' if agent_config.get('enable_shell') else '✗ Disabled'}\n\n"
        result += "Toolboxes:\n"
        for tb in agent_config.get('toolboxes', []):
            result += f"  • {tb}\n"
        return result
    
    # Return all commands (help must be first to override the built-in)
    return [show_help, list_tools, system_prompt_cmd, show_status, switch_model, memory_cmd, ollama_cmd, groq_cmd, rag_cmd, clear_screen, show_config]