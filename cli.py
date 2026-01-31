"""
CLI Template for Agent Forge Exports
====================================

This is the template CLI that gets copied/customized when exporting agents.
All //commands are implemented using the CommandRegistry from commands.py.

This file can be tested directly in langchain-agent-base, then exported agents
get a copy that's configured for their specific settings.
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Optional

try:
    from colorama import init, Fore, Style, Back, just_fix_windows_console
    just_fix_windows_console()
except (ImportError, AttributeError):
    from colorama import init, Fore, Style, Back
    init()

# Import prompt_toolkit for enhanced input with tab completion
try:
    from prompt_toolkit import prompt
    from prompt_toolkit.completion import PathCompleter, WordCompleter, Completer, Completion
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.document import Document
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

# Add langchain-agent-base to path
sys.path.insert(0, str(Path(__file__).parent / "langchain-agent-base" / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# Ensure Dynamic Toolbox storage is anchored to the agent directory.
# This prevents creating a `toolbox/` folder in whatever directory the user runs from.
if not os.getenv("CORE_CODER_TOOLBOX_DIR") and not os.getenv("LANGCHAIN_AGENT_BASE_TOOLBOX_DIR"):
    os.environ["CORE_CODER_TOOLBOX_DIR"] = str(Path(__file__).parent / "toolbox")

from langchain_core.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
from base import Agent
from toolbox import get_toolbox
from commands import CommandRegistry, command, create_cli_agent_commands

# For shell middleware
try:
    from langchain.agents.middleware import ShellToolMiddleware, HostExecutionPolicy
    SHELL_MIDDLEWARE_AVAILABLE = True
except ImportError:
    SHELL_MIDDLEWARE_AVAILABLE = False


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

CONFIG_FILE = Path(__file__).parent / "agent_config.json"

def load_config() -> dict:
    """Load agent configuration from JSON file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # Add default safe commands whitelist if not present
            if 'safe_commands' not in config:
                config['safe_commands'] = [
                    'date', 'Get-Date', 'time', 'pwd', 'Get-Location',
                    'ls', 'dir', 'Get-ChildItem', 'whoami', 'hostname',
                    'echo', 'Write-Output', 'cat', 'Get-Content',
                    'env', 'Get-Variable', 'python --version', 'node --version'
                ]
            
            # Add whitelist_enabled flag if not present (default: True)
            if 'whitelist_enabled' not in config:
                config['whitelist_enabled'] = True
            
            return config
    else:
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_FILE}")

def save_config(updates: dict = None):
    """Save configuration updates back to JSON file."""
    global AGENT_CONFIG
    if updates:
        AGENT_CONFIG.update(updates)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(AGENT_CONFIG, f, indent=2)

AGENT_CONFIG = load_config()


# ============================================================================
# SIMPLE CONVERSATION MEMORY
# ============================================================================

class SimpleConversationMemory:
    """Simple in-memory conversation history."""
    
    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self.history = {}
    
    def add_message(self, session_id: str, message: str, response: str):
        if session_id not in self.history:
            self.history[session_id] = []
        self.history[session_id].append({"message": message, "response": response})
        if len(self.history[session_id]) > self.max_messages:
            self.history[session_id] = self.history[session_id][-self.max_messages:]
    
    def get_history(self, session_id: str, limit: int = None) -> list:
        history = self.history.get(session_id, [])
        return history[-limit:] if limit else history
    
    def clear(self, session_id: str = None):
        if session_id:
            self.history.pop(session_id, None)
        else:
            self.history.clear()
    
    def get_message_count(self, session_id: str) -> int:
        return len(self.history.get(session_id, []))

_simple_memory = SimpleConversationMemory()


# ============================================================================
# CONFIRMATION CALLBACK HANDLER
# ============================================================================

class ConfirmationCallbackHandler(BaseCallbackHandler):
    """Callback handler that prompts for confirmation before tool execution."""
    
    def __init__(self, confirm_terminal: bool = False, confirm_tools: bool = False, colors=None):
        self.confirm_terminal = confirm_terminal
        self.confirm_tools = confirm_tools
        self.colors = colors
        self._pending_tools = []  # Collect all tools in current batch
        self._user_approved = None  # Store user's decision
        self._batch_started = False
        self._confirmation_shown = False
        self._showing_prompt = False  # Lock to prevent duplicate prompts
        self._safe_commands = AGENT_CONFIG.get('safe_commands', [])
    
    def _is_shell_tool(self, tool_name: str, tool_input: dict) -> bool:
        """Check if tool is a shell/terminal tool."""
        shell_keywords = [
            'shell', 'terminal', 'command', 'powershell', 'bash', 'cmd', 'run_',
            'execute', 'system', 'python_info', 'get_system', 'get_python',
            'install', 'pip', 'npm', 'git'
        ]
        tool_name_lower = tool_name.lower()
        return any(keyword in tool_name_lower for keyword in shell_keywords)
    
    def _is_safe_command(self, command: str) -> bool:
        """Check if command is in the safe whitelist."""
        if not command:
            return False
        
        # Extract base command (first word)
        base_cmd = command.strip().split()[0] if command.strip() else ''
        
        # Check against whitelist (case-insensitive)
        for safe_cmd in self._safe_commands:
            if base_cmd.lower() == safe_cmd.lower() or command.lower().startswith(safe_cmd.lower()):
                return True
        
        return False
    
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        """Called when tool execution starts - intercept and ask for confirmation."""
        tool_name = serialized.get('name', 'unknown')
        is_shell = self._is_shell_tool(tool_name, {})
        
        # Parse input to extract actual command
        import json
        actual_input = input_str
        try:
            # If input_str is a JSON dict, extract the command
            if isinstance(input_str, str) and input_str.strip().startswith('{'):
                input_dict = json.loads(input_str)
                if 'command' in input_dict:
                    actual_input = input_dict['command']
        except:
            pass  # Keep original input_str if parsing fails
        
        # Check if this is a safe whitelisted command (skip confirmation)
        if is_shell and AGENT_CONFIG.get('whitelist_enabled', True) and self._is_safe_command(actual_input):
            return  # Skip confirmation for safe commands
        
        # Check if confirmation needed
        needs_confirmation = (
            (is_shell and self.confirm_terminal) or
            (not is_shell and self.confirm_tools)
        )
        
        if needs_confirmation:
            
            # Add to pending tools list
            tool_type = "Terminal" if is_shell else "Tool"
            self._pending_tools.append({
                'name': tool_name,
                'input': actual_input,
                'type': tool_type
            })
            
            # Only the first tool shows the prompt
            if not self._showing_prompt and not self._confirmation_shown:
                self._showing_prompt = True  # Lock to prevent others from showing prompt
                
                import time
                time.sleep(0.2)  # Brief pause to collect other tools
                
                # Now show all pending tools and ask for confirmation
                self._confirmation_shown = True
                
                if self.colors:
                    c_warning = self.colors.get('warning')
                    c_info = self.colors.get('info')
                    c_success = self.colors.get('success')
                    c_error = self.colors.get('error')
                    c_shell = self.colors.get('shell')
                    c_primary = self.colors.get('primary')
                    c_accent = self.colors.get('accent')
                    c_secondary = self.colors.get('secondary')
                    c_reset = Style.RESET_ALL
                    
                    # Show "Agent:" label first
                    print(f"\n{c_secondary}Agent:{c_reset}")
                    
                    # Display all pending tools in a nice box
                    print(f"{c_warning}╭─ ⚠ Confirmation Required ─────────────────────────────────╮{c_reset}")
                    print(f"{c_warning}│{c_reset} {c_primary}The agent wants to execute {len(self._pending_tools)} tool(s):{c_reset}")
                    print(f"{c_warning}├────────────────────────────────────────────────────────────┤{c_reset}")
                    
                    for i, tool in enumerate(self._pending_tools, 1):
                        tool_color = c_shell if tool['type'] == 'Terminal' else c_accent
                        print(f"{c_warning}│{c_reset} {c_info}{i}.{c_reset} [{tool['type']}] {tool_color}{tool['name']}{c_reset}")
                        print(f"{c_warning}│{c_reset}    {c_primary}{tool['input']}{c_reset}")
                    
                    print(f"{c_warning}╰────────────────────────────────────────────────────────────╯{c_reset}")
                    
                    # Prompt for confirmation once for all tools
                    print(f"\n{c_info}You:{c_reset}")
                    while True:
                        response = input(f"{c_warning}Execute ALL these tools? (yes/no): {c_reset}").strip().lower()
                        
                        if response in ['yes', 'y']:
                            print(f"{c_success}✓ Approved - executing all tools...{c_reset}\n")
                            self._user_approved = True
                            break
                        elif response in ['no', 'n']:
                            print(f"{c_error}✗ Cancelled - blocking all tool execution{c_reset}\n")
                            self._user_approved = False
                            # Raise exception to stop all tool execution
                            raise KeyboardInterrupt("User cancelled tool execution")
                        else:
                            print("Please answer 'yes' or 'no'")
                else:
                    # Non-colored version
                    print(f"\nAgent:")
                    print(f"⚠ Confirmation Required")
                    print(f"The agent wants to execute {len(self._pending_tools)} tool(s):")
                    print("─" * 60)
                    
                    for i, tool in enumerate(self._pending_tools, 1):
                        print(f"{i}. [{tool['type']}] {tool['name']}")
                        print(f"   {tool['input']}")
                    
                    print("─" * 60)
                    print("\nYou:")
                    
                    while True:
                        response = input(f"Execute ALL these tools? (yes/no): ").strip().lower()
                        
                        if response in ['yes', 'y']:
                            print("✓ Approved - executing all tools...\n")
                            self._user_approved = True
                            break
                        elif response in ['no', 'n']:
                            print("✗ Cancelled - blocking all tool execution\n")
                            self._user_approved = False
                            raise KeyboardInterrupt("User cancelled tool execution")
                        else:
                            print("Please answer 'yes' or 'no'")
            else:
                # Subsequent tools: wait for the first tool to get user decision, then apply it
                import time
                while self._user_approved is None:
                    time.sleep(0.05)  # Wait for user response
                
                if self._user_approved is False:
                    raise KeyboardInterrupt("User cancelled tool execution")
    
    def on_chain_end(self, outputs, **kwargs) -> None:
        """Reset confirmation state after chain completes."""
        self._pending_tools = []
        self._confirmation_shown = False
        self._user_approved = None
        self._showing_prompt = False


# ============================================================================
# BANNER DISPLAY
# ============================================================================

def print_banner():
    """Display ASCII art banner and/or pixel art from config."""
    ascii_config = AGENT_CONFIG.get('ascii_art', {})
    banner_order = ascii_config.get('banner_order', 'banner-first')
    show_banner = ascii_config.get('show_font_banner') and ascii_config.get('font_banner')
    show_pixel = ascii_config.get('show_pixel_art') and ascii_config.get('pixel_art')
    
    def display_ascii_banner():
        if show_banner:
            color = ascii_config.get('font_banner_color', '#00FF00')
            banner_text = ascii_config.get('font_banner', '')
            if color.startswith('#') and len(color) == 7:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                print("\033[38;2;" + str(r) + ";" + str(g) + ";" + str(b) + "m" + banner_text + "\033[0m")
            else:
                print(banner_text)
            print()
    
    def display_pixel_art():
        if show_pixel:
            pixel_art = ascii_config.get('pixel_art', '')
            # Pixel art already contains actual ANSI escape characters from export
            print(pixel_art)
            print()
    
    if banner_order == 'pixel-first':
        display_pixel_art()
        display_ascii_banner()
    else:
        display_ascii_banner()
        display_pixel_art()


# ============================================================================
# AGENT FACTORY
# ============================================================================

def create_agent(project_root: str = ".", **kwargs):
    """Create agent instance from configuration."""
    
    # Load tools from configured toolboxes
    tools = []
    seen_tools = set()
    
    toolbox = get_toolbox()
    for toolbox_name in AGENT_CONFIG.get('toolboxes', ['coding']):
        try:
            category_tools = toolbox.get_tools_by_category(toolbox_name)
            for t in category_tools:
                tool_name = getattr(t, 'name', str(t))
                if tool_name not in seen_tools:
                    tools.append(t)
                    seen_tools.add(tool_name)
            print(f"✓ Loaded tools from '{toolbox_name}' toolbox")
        except Exception as e:
            print(f"⚠ Could not load toolbox '{toolbox_name}': {e}")
    
    print(f"✓ Total unique tools loaded: {len(tools)}")
    
    # Get config values
    enable_memory = kwargs.pop('enable_memory', AGENT_CONFIG.get('enable_memory', False))
    model_name = AGENT_CONFIG.get('model_name', 'openai/gpt-oss-120b')
    provider = AGENT_CONFIG.get('provider', 'groq')
    temperature = AGENT_CONFIG.get('temperature', 0.7)
    system_prompt = AGENT_CONFIG.get('system_prompt', 'You are a helpful assistant.')
    
    # Build agent parameters
    agent_params = {
        'name': AGENT_CONFIG.get('name', 'agent'),
        'system_prompt': system_prompt,
        'tools': tools,
        'model_name': model_name,
        'provider': provider,
        'temperature': temperature,
        'enable_memory': enable_memory,
    }
    
    # Add shell middleware if enabled
    if AGENT_CONFIG.get('enable_shell', True) and SHELL_MIDDLEWARE_AVAILABLE:
        agent_params['enable_shell_tool'] = True
        agent_params['workspace_root'] = project_root or '.'
        agent_params['shell_timeout'] = 120
        print(f"✓ Shell enabled with workspace: {agent_params['workspace_root']}")
    
    agent_params.update(kwargs)
    return Agent(**agent_params)


# ============================================================================
# AGENT COMMANDS (using CommandRegistry)
# ============================================================================

def setup_agent_commands(agent_instance, cli_instance) -> CommandRegistry:
    """
    Set up all //commands using the CommandRegistry system.
    Commands are defined in commands.py for maintainability.
    """
    registry = CommandRegistry()
    
    # Get CLI agent commands from commands.py factory
    agent_commands = create_cli_agent_commands(
        agent_instance=agent_instance,
        cli_instance=cli_instance,
        agent_config=AGENT_CONFIG,
        simple_memory=_simple_memory,
        save_config_fn=save_config
    )
    
    # Register all commands
    for cmd in agent_commands:
        registry.add_command(cmd)
    
    return registry


# ============================================================================
# COLOR SCHEMES
# ============================================================================

class Colors:
    """Handle color schemes for the CLI."""
    
    SCHEMES = {
        # Schemes will be populated from config
    }
    
    def __init__(self, scheme_name="default"):
        # Load custom scheme from config if available
        cli_appearance = AGENT_CONFIG.get('cli_appearance', {})
        colors = AGENT_CONFIG.get('colors', {})
        
        if colors:
            # Build custom scheme from config colors (from UI export)
            self.scheme = {
                "primary": self._hex_to_ansi(colors.get('primary', '#ffffff')),
                "secondary": self._hex_to_ansi(colors.get('secondary', '#aaaaaa')),
                "success": self._hex_to_ansi(colors.get('success', '#00ff00')),
                "error": self._hex_to_ansi(colors.get('error', '#ff0000')),
                "warning": self._hex_to_ansi(colors.get('warning', '#ffff00')),
                "info": self._hex_to_ansi(colors.get('info', '#00ffff')),
                "tool": self._hex_to_ansi(colors.get('tool', '#ff00ff')),
                "shell": self._hex_to_ansi(colors.get('shell', '#00ffff')),
                "accent": self._hex_to_ansi(colors.get('accent', '#00ff00')),
                # Aliases for backward compatibility
                "agent": self._hex_to_ansi(colors.get('primary', '#ffffff')),
                "user": self._hex_to_ansi(colors.get('info', '#00ffff')),
                "system": self._hex_to_ansi(colors.get('secondary', '#aaaaaa')),
                "command": self._hex_to_ansi(colors.get('accent', '#00ff00')),
                "output": self._hex_to_ansi(colors.get('success', '#00ff00')),
                "dim": Style.DIM,
                "reset": Style.RESET_ALL
            }
        else:
            # Fallback to default scheme if no colors in config
            self.scheme = self._get_default_scheme(scheme_name)
    
    def _hex_to_ansi(self, hex_color):
        """Convert hex color to ANSI escape sequence."""
        if hex_color.startswith('#') and len(hex_color) == 7:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            return f"\033[38;2;{r};{g};{b}m"
        return ''
    
    def _get_default_scheme(self, name):
        """Get a default color scheme."""
        schemes = {
            "dracula": {
                "agent": Fore.MAGENTA,
                "user": Fore.CYAN,
                "system": Fore.WHITE,
                "command": Fore.LIGHTYELLOW_EX,
                "tool": Fore.LIGHTMAGENTA_EX,
                "shell": Fore.LIGHTCYAN_EX,
                "output": Fore.LIGHTCYAN_EX,
                "error": Fore.RED,
                "success": Fore.GREEN,
                "warning": Fore.YELLOW,
                "dim": Style.DIM,
                "reset": Style.RESET_ALL
            },
            "default": {
                "agent": Fore.BLUE,
                "user": Fore.GREEN,
                "system": Fore.WHITE,
                "command": Fore.YELLOW,
                "tool": Fore.MAGENTA,
                "shell": Fore.CYAN,
                "output": Fore.CYAN,
                "error": Fore.RED,
                "success": Fore.GREEN,
                "warning": Fore.YELLOW,
                "dim": Style.DIM,
                "reset": Style.RESET_ALL
            }
        }
        return schemes.get(name, schemes["default"])
    
    def get(self, key):
        return self.scheme.get(key, '')


# ============================================================================
# AGENT CLI
# ============================================================================

class AgentCLI:
    """Interactive CLI using CommandRegistry for //commands."""
    
    def __init__(self, project_dir: str = ".", enable_memory: bool = True, session_id: str = None):
        """Initialize the CLI."""
        self.project_dir = Path(project_dir).resolve()
        self.enable_memory = enable_memory
        self.session_id = session_id or f"session_{AGENT_CONFIG.get('name', 'agent')}"
        
        # Confirmation settings
        self.confirm_terminal = AGENT_CONFIG.get("confirm_terminal", False)
        self.confirm_tools = AGENT_CONFIG.get("confirm_tools", False)
        
        # Setup colors
        cli_appearance = AGENT_CONFIG.get("cli_appearance", {})
        scheme_name = cli_appearance.get("color_scheme", "default")
        self.colors = Colors(scheme_name)
        self.c_agent = self.colors.get("agent")
        self.c_user = self.colors.get("user")
        self.c_sys = self.colors.get("system")
        self.c_err = self.colors.get("error")
        self.c_reset = self.colors.get("reset")
        
        # Verify API key
        if AGENT_CONFIG.get("provider") == "groq" and not os.getenv('GROQ_API_KEY'):
            print(f"{self.c_err}[ERROR] GROQ_API_KEY not found in environment{self.c_reset}")
            print("   Please create a .env file with your API key:")
            print("   GROQ_API_KEY=your_key_here")
            sys.exit(1)
        
        # Create agent
        display_name = AGENT_CONFIG.get('name', 'Agent')
        print(f"{self.c_sys}Initializing {display_name}...{self.c_reset}")
        self.agent = create_agent(
            project_root=str(self.project_dir),
            enable_memory=enable_memory
        )
        
        # Create confirmation callback handler
        self.confirmation_handler = ConfirmationCallbackHandler(
            confirm_terminal=self.confirm_terminal,
            confirm_tools=self.confirm_tools,
            colors=self.colors
        )
        
        # Setup command registry
        self.commands = setup_agent_commands(self.agent, self)
        
        # Setup input completer for tab completion
        if PROMPT_TOOLKIT_AVAILABLE:
            self._setup_completer()
        
        print(f"{self.colors.get('success')}Agent ready!{self.c_reset}\n")
    
    def _setup_completer(self):
        """Setup tab completion for //cd and other commands."""
        # Get list of command names for completion
        command_names = [f"//{cmd}" for cmd in self.commands.commands.keys()]
        self.command_completer = WordCompleter(
            command_names,
            ignore_case=True,
            sentence=True
        )
        self.path_completer = PathCompleter(expanduser=True)
        
        # Create custom context-aware completer
        class ContextAwareCompleter(Completer):
            """Completer that switches between command and path completion based on context."""
            def __init__(self, command_completer, path_completer):
                self.command_completer = command_completer
                self.path_completer = path_completer
            
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                
                # Check if we're completing a path after //cd
                if text.startswith('//cd '):
                    # Extract the path part after '//cd '
                    path_text = text[5:]  # Everything after '//cd '
                    # Create a new document with just the path
                    path_doc = Document(path_text, len(path_text))
                    for completion in self.path_completer.get_completions(path_doc, complete_event):
                        yield completion
                # If just starting or typing //, suggest commands
                elif text.startswith('//') or text == '' or text == '/':
                    for completion in self.command_completer.get_completions(document, complete_event):
                        yield completion
                # Otherwise, complete paths for regular input
                else:
                    for completion in self.path_completer.get_completions(document, complete_event):
                        yield completion
        
        self.context_completer = ContextAwareCompleter(self.command_completer, self.path_completer)
    
    def _get_input(self, prompt_text: str) -> str:
        """Get user input with smart tab completion."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return input(prompt_text).strip()
        
        try:
            result = prompt(
                ANSI(prompt_text),
                completer=self.context_completer,
                complete_while_typing=True,  # Show completions as you type
                enable_history_search=True,  # Enable Ctrl+R history search
                mouse_support=True,  # Enable mouse support for selection
            )
            return result.strip()
        except Exception:
            # Fallback to basic input if prompt_toolkit fails
            return input(prompt_text).strip()
    
    def update_confirmation_settings(self, confirm_terminal: bool = None, confirm_tools: bool = None):
        """Update confirmation settings and recreate callback handler."""
        if confirm_terminal is not None:
            self.confirm_terminal = confirm_terminal
        if confirm_tools is not None:
            self.confirm_tools = confirm_tools
        
        # Recreate callback handler with new settings
        self.confirmation_handler = ConfirmationCallbackHandler(
            confirm_terminal=self.confirm_terminal,
            confirm_tools=self.confirm_tools,
            colors=self.colors
        )
    
    def reinitialize_model(self):
        """Reinitialize the agent with the new model/provider."""
        try:
            print(f"\n{self.c_sys}Reinitializing agent with new model...{self.c_reset}")
            
            # Reload config from disk
            global AGENT_CONFIG
            AGENT_CONFIG = load_config()
            
            # Recreate agent
            self.agent = create_agent(
                project_root=str(self.project_dir),
                enable_memory=self.enable_memory
            )
            
            # Recreate command registry with new agent
            self.commands = setup_agent_commands(self.agent, self)
            
            print(f"{self.colors.get('success')}Model switched successfully!{self.c_reset}")
            print(f"{self.c_sys}Provider: {AGENT_CONFIG.get('provider')}{self.c_reset}")
            print(f"{self.c_sys}Model: {AGENT_CONFIG.get('model_name')}{self.c_reset}")
            return True
        except Exception as e:
            print(f"{self.c_err}Failed to reinitialize model: {e}{self.c_reset}")
            return False
    
    def run(self):
        """Run the interactive CLI."""
        # Display banner
        print_banner()
        
        # Display agent info with curved borders
        display_name = AGENT_CONFIG.get('name', 'Agent')
        c_primary = self.colors.get('primary')
        c_secondary = self.colors.get('secondary')
        c_accent = self.colors.get('accent')
        c_info = self.colors.get('info')
        c_success = self.colors.get('success')
        c_warning = self.colors.get('warning')
        c_reset = self.c_reset
        
        print(f"{c_accent}╭─────────────────────────────────────────────────────────────────────╮{c_reset}")
        print(f"{c_accent}│{c_reset} {c_primary}{display_name} - Interactive Mode{c_reset}")
        print(f"{c_accent}├─────────────────────────────────────────────────────────────────────┤{c_reset}")
        print(f"{c_accent}│{c_reset} {c_secondary}Provider:{c_reset} {c_info}{AGENT_CONFIG.get('provider', 'unknown')}{c_reset} {c_secondary}│{c_reset} {c_secondary}Model:{c_reset} {c_info}{AGENT_CONFIG.get('model_name', 'unknown')}{c_reset}")
        print(f"{c_accent}│{c_reset} {c_secondary}Memory:{c_reset} {c_success if self.enable_memory else c_warning}{'ON' if self.enable_memory else 'OFF'}{c_reset} {c_secondary}│{c_reset} {c_secondary}RAG:{c_reset} {c_success if AGENT_CONFIG.get('enable_rag') else c_warning}{'ON' if AGENT_CONFIG.get('enable_rag') else 'OFF'}{c_reset}")
        print(f"{c_accent}│{c_reset} {c_secondary}Confirm:{c_reset} Terminal={c_success if self.confirm_terminal else c_warning}{'ON' if self.confirm_terminal else 'OFF'}{c_reset} {c_secondary}│{c_reset} Tools={c_success if self.confirm_tools else c_warning}{'ON' if self.confirm_tools else 'OFF'}{c_reset}")
        print(f"{c_accent}╰─────────────────────────────────────────────────────────────────────╯{c_reset}")
        print()
        print(f"{c_secondary}Commands:{c_reset}")
        print(f"  {c_info}•{c_reset} Type your message and press Enter")
        print(f"  {c_info}•{c_reset} Type 'exit' or 'quit' to exit")
        print(f"  {c_info}•{c_reset} Type '//help' for special commands (//tools, //status, //config, etc.)")
        print()
        print(f"{c_accent}{'─' * 70}{c_reset}\n")
        
        while True:
            try:
                # Get user input with colored label and tab completion
                user_input = self._get_input(f"\n{self.colors.get('info')}You: {self.c_reset}")
                
                if not user_input:
                    continue
                
                # Handle special commands (//cmd format)
                if user_input.startswith('//'):
                    command_str = user_input[2:]
                    result = self.commands.execute_command(command_str)
                    print(f"\n{self.c_sys}{result}{self.c_reset}")
                    continue
                
                # Handle basic commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print(f"\n{self.c_sys}Goodbye!{self.c_reset}\n")
                    break
                
                if user_input.lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                
                # Send to agent with tool display and confirmation callback
                try:
                    result = self.agent.chat_with_tool_display(
                        user_input,
                        session_id=self.session_id,
                        tool_callback=self.print_tool_output,
                        callbacks=[self.confirmation_handler]
                    )
                    response = result.get('response', '')
                except AttributeError:
                    # Fallback if chat_with_tool_display not available
                    response = self.agent.chat(
                        user_input,
                        session_id=self.session_id,
                        callbacks=[self.confirmation_handler]
                    )
                
                # Store in memory
                if self.enable_memory:
                    _simple_memory.add_message(self.session_id, user_input, response)
                
                # Reset tool output flag for next interaction
                self._tools_started = False
                
                # Print agent response with colored label
                print(f"\n{self.colors.get('secondary')}Agent:{self.c_reset} ", end="")
                self.print_colorized_response(response)
                
            except KeyboardInterrupt:
                print(f"\n\n{self.c_sys}Goodbye!{self.c_reset}\n")
                break
            except Exception as e:
                print(f"\n{self.c_err}Error: {e}{self.c_reset}\n")
    
    def print_tool_output(self, tool_name, tool_input, tool_output):
        """Print tool outputs as they happen."""
        c_tool = self.colors.get("tool")
        c_output = self.colors.get("output")
        c_secondary = self.colors.get("secondary")
        
        # Show Agent label before first tool
        if not hasattr(self, '_tools_started'):
            self._tools_started = True
            print(f"\n{c_secondary}Agent:{self.c_reset}")
        
        print(f"{c_tool}╭─ Tool: {tool_name} ─╮{self.c_reset}")
        if tool_output:
            lines = str(tool_output).split('\n')
            for line in lines:
                print(f"{c_output}│ {line}{self.c_reset}")
        print(f"{c_tool}╰{'─' * (len(tool_name) + 12)}╯{self.c_reset}")
    
    def print_colorized_response(self, response: str):
        """Print response with colorized shell commands and output."""
        c_cmd = self.colors.get("command")
        c_out = self.colors.get("output") 
        c_primary = self.colors.get("primary")  # Use primary for agent text
        c_reset = self.c_reset
        
        in_code_block = False
        for line in response.split('\n'):
            stripped = line.strip()
            
            # Check for code block start/end
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                print(f"{c_out}{line}{c_reset}")
            # Inside code block
            elif in_code_block:
                if stripped.startswith('$ ') or stripped.startswith('> ') or stripped.startswith('PS '):
                    print(f"{c_cmd}{line}{c_reset}")
                else:
                    print(f"{c_out}{line}{c_reset}")
            # Shell command lines outside code blocks
            elif stripped.startswith('$ '):
                print(f"{c_cmd}{line}{c_reset}")
            # Regular agent text
            else:
                print(f"{c_primary}{line}{c_reset}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description=f"{AGENT_CONFIG.get('name', 'Agent')} - CLI Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py                          # Start interactive mode
  python cli.py --no-memory              # Start without memory
  python cli.py /path/to/project         # Specify project directory
  python cli.py --session my_session     # Custom session ID
        """
    )
    
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Project directory (default: current directory)"
    )
    
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable memory and RAG"
    )
    
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Custom session ID"
    )
    
    args = parser.parse_args()
    
    # Validate project directory
    project_path = Path(args.project_dir).resolve()
    if not project_path.exists():
        print(f"❌ Error: Directory does not exist: {args.project_dir}")
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"❌ Error: Not a directory: {args.project_dir}")
        sys.exit(1)
    
    # Start CLI
    enable_memory = not args.no_memory
    cli = AgentCLI(
        str(project_path),
        enable_memory=enable_memory,
        session_id=args.session
    )
    cli.run()


if __name__ == "__main__":
    main()
