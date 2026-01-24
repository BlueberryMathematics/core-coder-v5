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

try:
    from colorama import Style
except ImportError:
    class Style:
        DIM = ''
        RESET_ALL = ''


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
            command_str: Command string (with or without /) and arguments
            **kwargs: Additional command arguments
            
        Returns:
            Command result as string
        """
        # Remove leading / if present and split into parts
        command_str = command_str.lstrip('/')
        parts = command_str.split()
        
        if not parts:
            return "No command provided"
        
        command_name = parts[0]
        command_args = parts[1:] if len(parts) > 1 else []
        
        if command_name not in self.commands:
            available = ', '.join(self.commands.keys())
            return f"Command '{command_name}' not found. Available commands: {available}"
        
        command_info = self.commands[command_name]
        
        try:
            # Build kwargs from command_args if not already provided
            if not kwargs and command_args:
                # Map positional args to parameter names
                param_names = list(command_info.parameters.keys())
                for i, arg in enumerate(command_args):
                    if i < len(param_names):
                        kwargs[param_names[i]] = arg
            
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
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_secondary = c.get('secondary')
        c_info = c.get('info')
        c_success = c.get('success')
        c_reset = c.get('reset')
        
        if command_name:
            return f"{c_secondary}Help for specific commands: Use //list to see all commands{c_reset}"
        
        # Full formatted help display with colors
        result = f"\n{c_accent}╭{'─'*68}╮\n"
        result += f"│  {c_primary}{agent_config.get('name', 'Agent')} - Help{' ' * (62 - len(agent_config.get('name', 'Agent')))}{c_accent}│\n"
        result += f"╰{'─'*68}╯{c_reset}\n\n"
        
        result += f"{c_info}Basic Commands:{c_reset}\n"
        result += f"{c_secondary}  exit, quit, q  - Exit the CLI{c_reset}\n"
        result += f"{c_secondary}  clear          - Clear the screen{c_reset}\n"
        result += f"{c_secondary}  help           - Show this help message{c_reset}\n\n"
        
        result += f"{c_info}Special Commands (// prefix):{c_reset}\n"
        result += f"{c_accent}  //tools{c_reset}        {c_secondary}- List all available tools{c_reset}\n"
        result += f"{c_accent}  //system_prompt {c_accent}<new_prompt_optional>{c_reset} {c_secondary}- Show or set the system prompt{c_reset}\n"
        result += f"{c_accent}  //status{c_reset}       {c_secondary}- Show agent status and configuration{c_reset}\n"
        result += f"{c_accent}  //config{c_reset}       {c_secondary}- Show full configuration{c_reset}\n"
        result += f"{c_accent}  //confirm      {c_accent}terminal|tools <on|off>{c_reset} {c_secondary}- Control confirmation prompts{c_reset}\n"
        result += f"{c_accent}  //whitelist    {c_accent}<on|off|list|add|remove> [command]{c_reset} {c_secondary}- Manage safe command whitelist{c_reset}\n"
        result += f"{c_accent}  //ollama       {c_accent}list{c_reset} {c_secondary}- List available Ollama models{c_reset}\n"
        result += f"{c_accent}  //groq         {c_accent}list{c_reset} {c_secondary}- List available Groq models{c_reset}\n"
        result += f"{c_accent}  //model        {c_accent}<provider> <name>{c_reset} {c_secondary}- Switch provider and model{c_reset}\n"
        result += f"{c_accent}  //memory       {c_accent}status|clear|show{c_reset} {c_secondary}- Manage conversation memory{c_reset}\n"
        result += f"{c_accent}  //rag          {c_accent}status|search <query>{c_reset} {c_secondary}- RAG knowledge base{c_reset}\n"
        result += f"{c_accent}  //clear{c_reset}        {c_secondary}- Clear the screen{c_reset}\n"
        result += f"{c_accent}  //help{c_reset}         {c_secondary}- Show this help{c_reset}\n\n"
        
        result += f"{c_info}Agent Features:{c_reset}\n"
        result += f"{c_secondary}  - Provider: {c_accent}{agent_config.get('provider', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}  - Model: {c_accent}{agent_config.get('model_name', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}  - Temperature: {c_primary}{agent_config.get('temperature', 0.0)}{c_reset}\n"
        result += f"{c_secondary}  - Memory: {c_success if cli_instance.enable_memory else c.get('warning')}{'Enabled' if cli_instance.enable_memory else 'Disabled'}{c_reset}\n"
        
        # Show message count if memory is enabled
        if simple_memory and cli_instance.enable_memory:
            history = simple_memory.get_history(cli_instance.session_id)
            if history:
                result += f"{c_secondary}    └─ Messages in context: {c_primary}{len(history)}{c_reset}\n"
        
        result += f"{c_secondary}  - RAG: {c_success if agent_config.get('enable_rag') else c.get('warning')}{'Enabled' if agent_config.get('enable_rag') else 'Disabled'}{c_reset}\n"
        
        # Show tool count
        try:
            tool_count = len(agent_instance.tools) if hasattr(agent_instance, 'tools') else 0
            result += f"{c_secondary}  - Tools: {c_primary}{tool_count} available{c_reset}\n"
        except:
            result += f"{c_secondary}  - Tools: Available{c_reset}\n"
        
        result += f"\n{c_accent}╰{'─'*68}╯{c_reset}"
        return result
    
    # Tools command
    @command("tools", "List all available tools")
    def list_tools() -> str:
        try:
            c = cli_instance.colors
            c_primary = c.get('primary')
            c_accent = c.get('accent')
            c_info = c.get('info')
            c_secondary = c.get('secondary')
            c_reset = c.get('reset')
            
            tools = agent_instance.list_tools()
            if tools:
                result = f"\n{c_accent}╭{'─'*62}╮\n"
                result += f"│{c_primary}                    🛠️  Available Tools                    {c_accent}│\n"
                result += f"╰{'─'*62}╯{c_reset}\n\n"
                for i, tool_name in enumerate(tools, 1):
                    result += f"{c_secondary}{i:4}.{c_reset} {c_info}{tool_name}{c_reset}\n"
                result += f"\n{c_accent}Total: {c_primary}{len(tools)}{c_accent} tools loaded{c_reset}"
                return result
            else:
                return f"{c_secondary}No tools currently loaded{c_reset}"
        except Exception as e:
            return f"Unable to list tools: {e}"
    
    # System Prompt command
    @command("system_prompt", "Show or set the system prompt", "//system_prompt [new_prompt]")
    def system_prompt_cmd(new_prompt: str = None) -> str:
        # Get colors from CLI instance
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_success = c.get('success')
        c_info = c.get('info')
        c_warning = c.get('warning')
        c_secondary = c.get('secondary')
        c_reset = c.get('reset')
        
        if new_prompt:
            agent_config['system_prompt'] = new_prompt
            save_config_fn()
            cli_instance.reinitialize_model()  # Rebuild agent with new prompt
            return f"{c_success}✓ System prompt updated and agent reinitialized{c_reset}"
        else:
            # Show the full assembled system prompt (all parts like in UI) with colors
            result = f"\n{c_accent}╭{'─'*62}╮\n"
            result += f"│{c_primary}              📋 Agent System Prompt (Full)                {c_accent}│\n"
            result += f"╰{'─'*62}╯{c_reset}\n\n"
            
            # Show all parts that get assembled into the actual prompt
            if agent_config.get('prompt_opening'):
                result += f"{c_info}═══ Opening (before your prompt) ═══{c_reset}\n"
                result += f"{c_secondary}{agent_config['prompt_opening'].replace('{agentName}', agent_config.get('name', 'Agent'))}{c_reset}"
                result += "\n\n"
            
            result += f"{c_accent}═══ Your Core Instructions ═══{c_reset}\n"
            result += f"{c_primary}{agent_config.get('system_prompt', 'Not set')}{c_reset}"
            result += "\n\n"
            
            if agent_config.get('enable_shell', True) and agent_config.get('prompt_shell'):
                result += f"{c_warning}═══ Shell Instructions (when enabled) ═══{c_reset}\n"
                result += f"{c_secondary}{agent_config['prompt_shell']}{c_reset}"
                result += "\n\n"
            
            if agent_config.get('prompt_closing'):
                result += f"{c_success}═══ Closing ═══{c_reset}\n"
                result += f"{c_secondary}{agent_config['prompt_closing']}{c_reset}"
                result += "\n\n"
            
            result += f"{Style.DIM}Note: System context (OS, Shell, Python info) is added automatically at startup.{c_reset}\n"
            
            return result
    
    # Status command
    @command("status", "Show agent status and configuration")
    def show_status() -> str:
        # Get colors from CLI instance
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_success = c.get('success')
        c_info = c.get('info')
        c_warning = c.get('warning')
        c_secondary = c.get('secondary')
        c_reset = c.get('reset')
        
        result = f"\n{c_accent}╭{'─'*62}╮\n"
        result += f"│{c_primary}                    Agent Status                            {c_accent}│\n"
        result += f"╰{'─'*62}╯{c_reset}\n\n"
        result += f"{c_secondary}Name:        {c_primary}{agent_config.get('name', 'Agent')}{c_reset}\n"
        result += f"{c_secondary}Provider:    {c_accent}{agent_config.get('provider', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}Model:       {c_accent}{agent_config.get('model_name', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}Temperature: {c_warning}{agent_config.get('temperature', 0.0)}{c_reset}\n"
        result += f"{c_secondary}Memory:      {c_success if cli_instance.enable_memory else c_warning}{'Enabled' if cli_instance.enable_memory else 'Disabled'}{c_reset}\n"
        result += f"{c_secondary}RAG:         {c_success if agent_config.get('enable_rag') else c_warning}{'Enabled' if agent_config.get('enable_rag') else 'Disabled'}{c_reset}\n"
        result += f"{c_secondary}Confirm:     Terminal={c_success if cli_instance.confirm_terminal else c_warning}{'ON' if cli_instance.confirm_terminal else 'OFF'}{c_reset} | Tools={c_success if cli_instance.confirm_tools else c_warning}{'ON' if cli_instance.confirm_tools else 'OFF'}{c_reset}\n"
        result += f"{c_secondary}Session:     {c_info}{cli_instance.session_id}{c_reset}\n"
        msg_count = len(simple_memory.get_history(cli_instance.session_id)) if simple_memory and cli_instance.enable_memory else 0
        result += f"{c_secondary}Messages in context: {c_primary}{msg_count}{c_reset}\n"
        result += f"{c_secondary}Current working directory: {c_info}{os.getcwd()}{c_reset}\n"
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
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_info = c.get('info')
        c_secondary = c.get('secondary')
        c_error = c.get('error')
        c_reset = c.get('reset')
        
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
                    output = f"\n{c_accent}╭{'─'*62}╮\n"
                    output += f"│{c_primary}                 🦙 Available Ollama Models                {c_accent}│\n"
                    output += f"╰{'─'*62}╯{c_reset}\n\n"
                    output += f"{c_info}{result.stdout}{c_reset}"
                    return output
                return f"{c_error}Error listing Ollama models: {result.stderr}{c_reset}"
            except FileNotFoundError:
                return f"{c_error}Ollama is not installed or not in PATH{c_reset}"
            except Exception as e:
                return f"{c_error}Error: {e}{c_reset}"
        return f"Unknown ollama action: {action}"
    
    # Groq command
    @command("groq", "Manage Groq models", "//groq list")
    def groq_cmd(action: str = "list") -> str:
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_info = c.get('info')
        c_secondary = c.get('secondary')
        c_reset = c.get('reset')
        
        if action == "list":
            result = f"\n{c_accent}╭{'─'*62}╮\n"
            result += f"│{c_primary}                  ⚡ Available Groq Models                  {c_accent}│\n"
            result += f"╰{'─'*62}╯{c_reset}\n\n"
            result += f"{c_info}Primary Models:{c_reset}\n"
            result += f"{c_info}  • {c_secondary}llama-3.3-70b-versatile{c_reset} {c_primary}(Recommended){c_reset}\n"
            result += f"{c_info}  • {c_secondary}llama-3.1-70b-versatile{c_reset}\n"
            result += f"{c_info}  • {c_secondary}llama-3.1-8b-instant{c_reset}\n"
            result += f"{c_info}  • {c_secondary}mixtral-8x7b-32768{c_reset}\n"
            result += f"{c_info}  • {c_secondary}gemma2-9b-it{c_reset}\n"
            result += f"{c_info}  • {c_secondary}qwen/qwen3-32b{c_reset}\n"
            result += f"{c_info}  • {c_secondary}openai/gpt-oss-120b{c_reset}\n"
            result += f"{c_info}  • {c_secondary}openai/gpt-oss-20b{c_reset}\n\n"
            result += f"{c_info}Specialized Models:{c_reset}\n"
            result += f"{c_info}  • {c_secondary}groq/compound{c_reset}\n"
            result += f"{c_info}  • {c_secondary}groq/compound-mini{c_reset}\n"
            result += f"{c_info}  • {c_secondary}meta-llama/llama-4-maverick-17b-128e-instruct{c_reset}\n"
            result += f"{c_info}  • {c_secondary}meta-llama/llama-4-scout-17b-16e-instruct{c_reset}\n"
            result += f"{c_info}  • {c_secondary}meta-llama/llama-guard-4-12b{c_reset}\n"
            result += f"{c_info}  • {c_secondary}meta-llama/llama-prompt-guard-2-22m{c_reset}\n"
            result += f"{c_info}  • {c_secondary}meta-llama/llama-prompt-guard-2-86m{c_reset}\n"
            result += f"{c_info}  • {c_secondary}openai/gpt-oss-safeguard-20b{c_reset}\n"
            result += f"\n{c_accent}Use:{c_reset} {c_secondary}//model groq <model_name>{c_reset}"
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
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_success = c.get('success')
        c_info = c.get('info')
        c_warning = c.get('warning')
        c_secondary = c.get('secondary')
        c_reset = c.get('reset')
        
        result = f"\n{c_accent}╭{'─'*62}╮\n"
        result += f"│{c_primary}                  ⚙️  Agent Configuration                   {c_accent}│\n"
        result += f"╰{'─'*62}╯{c_reset}\n\n"
        result += f"{c_info}Core Settings:{c_reset}\n"
        result += f"{c_secondary}  Name:{c_reset}        {c_primary}{agent_config.get('name', 'N/A')}{c_reset}\n"
        result += f"{c_secondary}  Provider:{c_reset}    {c_accent}{agent_config.get('provider', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}  Model:{c_reset}       {c_accent}{agent_config.get('model_name', 'unknown')}{c_reset}\n"
        result += f"{c_secondary}  Temperature:{c_reset} {c_warning}{agent_config.get('temperature', 0.0)}{c_reset}\n\n"
        result += f"{c_info}Features:{c_reset}\n"
        mem_icon = '✓' if agent_config.get('enable_memory') else '✗'
        rag_icon = '✓' if agent_config.get('enable_rag') else '✗'
        shell_icon = '✓' if agent_config.get('enable_shell') else '✗'
        result += f"{c_secondary}  Memory:{c_reset} {c_success if agent_config.get('enable_memory') else c_warning}{mem_icon} {'Enabled' if agent_config.get('enable_memory') else 'Disabled'}{c_reset}\n"
        result += f"{c_secondary}  RAG:{c_reset}    {c_success if agent_config.get('enable_rag') else c_warning}{rag_icon} {'Enabled' if agent_config.get('enable_rag') else 'Disabled'}{c_reset}\n"
        result += f"{c_secondary}  Shell:{c_reset}  {c_success if agent_config.get('enable_shell') else c_warning}{shell_icon} {'Enabled' if agent_config.get('enable_shell') else 'Disabled'}{c_reset}\n\n"
        result += f"{c_info}Toolboxes:{c_reset}\n"
        for tb in agent_config.get('toolboxes', []):
            result += f"{c_accent}  • {tb}{c_reset}\n"
        return result
    
    # Confirm command - control confirmation prompts for terminal and tools
    @command("confirm", "Control confirmation prompts", "//confirm <terminal|tools> <on|off>")
    def confirm_cmd(target: str = None, state: str = None) -> str:
        """
        Enable or disable confirmation prompts for terminal commands and tools.
        
        Usage:
            //confirm terminal on   - Enable confirmation for terminal commands
            //confirm terminal off  - Disable confirmation for terminal commands
            //confirm tools on      - Enable confirmation for all other tools
            //confirm tools off     - Disable confirmation for all other tools
            //confirm               - Show current status
        """
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_success = c.get('success')
        c_info = c.get('info')
        c_warning = c.get('warning')
        c_secondary = c.get('secondary')
        c_reset = c.get('reset')
        
        if not target:
            # Show current status with colors
            terminal_status = f"{c_success}ON{c_reset}" if cli_instance.confirm_terminal else f"{c_warning}OFF{c_reset}"
            tools_status = f"{c_success}ON{c_reset}" if cli_instance.confirm_tools else f"{c_warning}OFF{c_reset}"
            whitelist_enabled = agent_config.get('whitelist_enabled', True)
            whitelist_status = f"{c_success}ENABLED{c_reset}" if whitelist_enabled else f"{c_warning}DISABLED{c_reset}"
            safe_count = len(agent_config.get('safe_commands', []))
            
            result = f"\n{c_accent}╭{'─'*62}╮\n"
            result += f"│{c_primary}              🛡️  Confirmation Settings                     {c_accent}│\n"
            result += f"╰{'─'*62}╯{c_reset}\n\n"
            result += f"{c_info}Confirmation Modes:{c_reset}\n"
            result += f"{c_secondary}  Terminal Commands:{c_reset} {terminal_status}\n"
            result += f"{c_secondary}  Other Tools:{c_reset}       {tools_status}\n\n"
            result += f"{c_info}Safe Command Whitelist:{c_reset} {whitelist_status}\n"
            result += f"{c_secondary}  {safe_count} safe commands (no confirmation needed){c_reset}\n"
            result += f"{c_accent}  Use //whitelist to manage safe commands{c_reset}\n\n"
            result += f"{c_secondary}Usage:{c_reset}\n"
            result += f"{c_accent}  //confirm terminal on/off{c_reset}  - Toggle terminal confirmation\n"
            result += f"{c_accent}  //confirm tools on/off{c_reset}     - Toggle tools confirmation\n"
            return result
        
        if target.lower() not in ['terminal', 'tools']:
            return f"{c.get('error')}Error: Target must be 'terminal' or 'tools'\nUsage: //confirm <terminal|tools> <on|off>{c_reset}"
        
        if not state or state.lower() not in ['on', 'off']:
            return f"{c.get('error')}Error: State must be 'on' or 'off'\nUsage: //confirm <terminal|tools> <on|off>{c_reset}"
        
        is_on = state.lower() == 'on'
        
        # Update the setting
        if target.lower() == 'terminal':
            cli_instance.confirm_terminal = is_on
            agent_config['confirm_terminal'] = is_on
            msg = f"{c_info}Terminal command confirmation:{c_reset} {c_success if is_on else c_warning}{'ENABLED' if is_on else 'DISABLED'}{c_reset}"
        else:  # tools
            cli_instance.confirm_tools = is_on
            agent_config['confirm_tools'] = is_on
            msg = f"{c_info}Tool confirmation:{c_reset} {c_success if is_on else c_warning}{'ENABLED' if is_on else 'DISABLED'}{c_reset}"
        
        # Save to config file
        save_config_fn(agent_config)
        
        # Update confirmation callback handler with new settings
        cli_instance.update_confirmation_settings(
            confirm_terminal=agent_config.get('confirm_terminal'),
            confirm_tools=agent_config.get('confirm_tools')
        )
        
        return f"\n{c_success}✓{c_reset} {msg}\n{c_secondary}  Settings saved to agent_config.json{c_reset}"
    
    # Whitelist command - manage safe commands that skip confirmation
    @command("whitelist", "Manage safe command whitelist", "//whitelist <on|off|list|add|remove> [command]")
    def whitelist_cmd(action: str = "list", command: str = None) -> str:
        """
        Manage the whitelist of safe commands that don't require confirmation.
        
        Usage:
            //whitelist              - Show all whitelisted commands
            //whitelist on           - Enable whitelist (safe commands skip confirmation)
            //whitelist off          - Disable whitelist (all commands require confirmation)
            //whitelist list         - Show all whitelisted commands
            //whitelist add <cmd>    - Add command to whitelist
            //whitelist remove <cmd> - Remove command from whitelist
        """
        c = cli_instance.colors
        c_primary = c.get('primary')
        c_accent = c.get('accent')
        c_success = c.get('success')
        c_info = c.get('info')
        c_warning = c.get('warning')
        c_secondary = c.get('secondary')
        c_error = c.get('error')
        c_reset = c.get('reset')
        
        safe_commands = agent_config.get('safe_commands', [])
        whitelist_enabled = agent_config.get('whitelist_enabled', True)
        
        if action.lower() == 'on':
            agent_config['whitelist_enabled'] = True
            save_config_fn(agent_config)
            return f"\n{c_success}✓ Whitelist ENABLED{c_reset}\n{c_secondary}  Safe commands will skip confirmation{c_reset}"
        
        elif action.lower() == 'off':
            agent_config['whitelist_enabled'] = False
            save_config_fn(agent_config)
            return f"\n{c_warning}✗ Whitelist DISABLED{c_reset}\n{c_secondary}  All commands will require confirmation (if enabled){c_reset}"
        
        elif action.lower() == 'list' or not action:
            status_text = f"{c_success}ENABLED{c_reset}" if whitelist_enabled else f"{c_warning}DISABLED{c_reset}"
            result = f"\n{c_accent}╭{'─'*62}╮\n"
            result += f"│{c_primary}              ✅ Safe Command Whitelist                    {c_accent}│\n"
            result += f"╰{'─'*62}╯{c_reset}\n\n"
            result += f"{c_info}Status:{c_reset} {status_text}\n"
            result += f"{c_secondary}These commands execute without confirmation:{c_reset}\n\n"
            
            for i, cmd in enumerate(safe_commands, 1):
                result += f"{c_info}{i:3}.{c_reset} {c_secondary}{cmd}{c_reset}\n"
            
            result += f"\n{c_accent}Total: {c_primary}{len(safe_commands)}{c_accent} safe commands{c_reset}\n\n"
            result += f"{c_secondary}Usage:{c_reset}\n"
            result += f"{c_accent}  //whitelist on{c_reset}             - Enable whitelist\n"
            result += f"{c_accent}  //whitelist off{c_reset}            - Disable whitelist\n"
            result += f"{c_accent}  //whitelist add <command>{c_reset}    - Add to whitelist\n"
            result += f"{c_accent}  //whitelist remove <command>{c_reset} - Remove from whitelist\n"
            result += f"{c_accent}  //whitelist list{c_reset}             - Show all whitelisted commands\n"
            return result
        
        elif action.lower() == 'add':
            if not command:
                return f"{c_error}Error: Please specify a command to add\nUsage: //whitelist add <command>{c_reset}"
            
            if command in safe_commands:
                return f"{c_warning}Command '{command}' is already in the whitelist{c_reset}"
            
            safe_commands.append(command)
            agent_config['safe_commands'] = safe_commands
            save_config_fn(agent_config)
            
            # Update the confirmation handler's whitelist
            if hasattr(cli_instance, 'confirmation_handler'):
                cli_instance.confirmation_handler._safe_commands = safe_commands
            
            return f"\n{c_success}✓ Added '{command}' to safe whitelist{c_reset}\n{c_secondary}  This command will no longer require confirmation{c_reset}"
        
        elif action.lower() == 'remove':
            if not command:
                return f"{c_error}Error: Please specify a command to remove\nUsage: //whitelist remove <command>{c_reset}"
            
            if command not in safe_commands:
                return f"{c_error}Command '{command}' is not in the whitelist{c_reset}"
            
            safe_commands.remove(command)
            agent_config['safe_commands'] = safe_commands
            save_config_fn(agent_config)
            
            # Update the confirmation handler's whitelist
            if hasattr(cli_instance, 'confirmation_handler'):
                cli_instance.confirmation_handler._safe_commands = safe_commands
            
            return f"\n{c_success}✓ Removed '{command}' from whitelist{c_reset}\n{c_secondary}  This command will now require confirmation (if enabled){c_reset}"
        
        else:
            return f"{c_error}Unknown action: {action}\nUsage: //whitelist <list|add|remove> [command]{c_reset}"
    
    # Return all commands (help must be first to override the built-in)
    return [show_help, list_tools, system_prompt_cmd, show_status, switch_model, memory_cmd, ollama_cmd, groq_cmd, rag_cmd, clear_screen, show_config, confirm_cmd, whitelist_cmd]