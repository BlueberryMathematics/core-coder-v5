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

from dotenv import load_dotenv
load_dotenv()

# Add langchain-agent-base to path
sys.path.insert(0, str(Path(__file__).parent / "langchain-agent-base" / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from langchain_core.tools import tool
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
            return json.load(f)
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
        
        if colors and scheme_name == 'custom':
            # Build custom scheme from config colors
            self.scheme = self._build_custom_scheme(colors)
        else:
            self.scheme = self._get_default_scheme(scheme_name)
    
    def _build_custom_scheme(self, colors):
        """Build a color scheme from config colors."""
        return {
            "agent": self._hex_to_ansi(colors.get('primary', '#00ff41')),
            "user": self._hex_to_ansi(colors.get('info', colors.get('secondary', '#ffffff'))),
            "system": self._hex_to_ansi(colors.get('secondary', '#ffffff')),
            "command": self._hex_to_ansi(colors.get('accent', '#00d9ff')),
            "tool": self._hex_to_ansi(colors.get('tool', '#FFB86C')),
            "shell": self._hex_to_ansi(colors.get('shell', '#00DDDD')),
            "output": self._hex_to_ansi(colors.get('success', '#00FF00')),
            "error": self._hex_to_ansi(colors.get('error', '#ff5555')),
            "success": self._hex_to_ansi(colors.get('success', '#55ff55')),
            "warning": self._hex_to_ansi(colors.get('warning', '#ffff55')),
            "dim": Style.DIM,
            "reset": Style.RESET_ALL
        }
    
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
        
        # Setup command registry
        self.commands = setup_agent_commands(self.agent, self)
        
        print(f"{self.colors.get('success')}Agent ready!{self.c_reset}\n")
    
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
        
        # Display agent info
        display_name = AGENT_CONFIG.get('name', 'Agent')
        print(f"{self.c_sys}{'='*70}")
        print(f"  {display_name} - Interactive Mode")
        print(f"  Provider: {AGENT_CONFIG.get('provider', 'unknown')} | Model: {AGENT_CONFIG.get('model_name', 'unknown')}")
        print(f"  Memory: {'ON' if self.enable_memory else 'OFF'} | RAG: {'ON' if AGENT_CONFIG.get('enable_rag') else 'OFF'}")
        print(f"{'='*70}{self.c_reset}")
        print()
        print(f"{self.c_sys}Commands:")
        print("  - Type your message and press Enter")
        print("  - Type 'exit' or 'quit' to exit")
        print("  - Type '//help' for special commands (//tools, //status, //config, etc.){self.c_reset}")
        print()
        print(f"{self.c_sys}{'='*70}{self.c_reset}\n")
        
        while True:
            try:
                # Get user input
                user_input = input(f"\n{self.c_user}You: {self.c_reset}").strip()
                
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
                
                # Send to agent with tool display
                try:
                    result = self.agent.chat_with_tool_display(
                        user_input,
                        session_id=self.session_id,
                        tool_callback=self.print_tool_output
                    )
                    response = result.get('response', '')
                except AttributeError:
                    # Fallback if chat_with_tool_display not available
                    response = self.agent.chat(user_input, session_id=self.session_id)
                
                # Store in memory
                if self.enable_memory:
                    _simple_memory.add_message(self.session_id, user_input, response)
                
                # Print agent response
                print(f"\n{self.c_agent}Agent: {self.c_reset}")
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
        print(f"\n{c_tool}╭─ Tool: {tool_name} ─╮{self.c_reset}")
        if tool_output:
            lines = str(tool_output).split('\n')
            for line in lines:
                print(f"{c_output}│ {line}{self.c_reset}")
        print(f"{c_tool}╰{'─' * (len(tool_name) + 12)}╯{self.c_reset}")
    
    def print_colorized_response(self, response: str):
        """Print response with colorized shell commands and output."""
        c_cmd = self.colors.get("command")
        c_out = self.colors.get("output") 
        c_agent = self.c_agent
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
                print(f"{c_agent}{line}{c_reset}")


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
