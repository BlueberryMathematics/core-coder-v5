"""
Agent Configuration System
==========================

JSON-based configuration for agents that standardizes:
- UI exports (Core Coder v3, etc.)
- CLI usage (cli_coding_agent.py)
- Programmatic agent creation

All configurations use the same JSON schema for consistency.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class AgentConfig:
    """
    Standardized agent configuration.
    
    This is the same format used by:
    - Agent Forge UI exports
    - CLI coding agent
    - Programmatic agent creation
    """
    
    # Agent identity
    name: str = "Coding Master"
    version: str = "1.0.0"
    description: str = "CLI-first coding assistant"
    author: str = "Agent Forge"
    category: str = "coding"
    
    # Base agent settings
    base_agent: str = "create_ultimate_coding_agent"  # Factory function name
    model_name: str = "openai/gpt-oss-120b"
    provider: str = "groq"
    temperature: float = 0.1
    
    # Project settings
    project_root: Optional[str] = None
    workspace_root: Optional[str] = None
    
    # Feature flags
    enable_shell: bool = True
    enable_file_ops: bool = True
    enable_memory: bool = True
    enable_rag: bool = False
    enable_commands: bool = True
    
    # Toolboxes to load
    toolboxes: List[str] = field(default_factory=lambda: ["coding", "math", "science"])
    
    # Custom tools (LLM-generated or manual)
    custom_tools: List[Dict[str, Any]] = field(default_factory=list)
    
    # =========================================================================
    # SYSTEM PROMPT CUSTOMIZATION
    # =========================================================================
    # Core instructions - the main personality/behavior text
    system_prompt: str = ""
    
    # Auto-enhancement sections (set to False to disable, or string to customize)
    # Opening: Introduces the agent by name
    prompt_opening: Any = None  # None = use default, False = disable, str = custom
    
    # Shell instructions: Explains shell capabilities (only used if enable_shell=True)
    prompt_shell: Any = None  # None = use default, False = disable, str = custom
    
    # Closing: Final behavioral instructions
    prompt_closing: Any = None  # None = use default, False = disable, str = custom
    
    # =========================================================================
    # MIDDLEWARE & MEMORY
    # =========================================================================
    # Middleware configuration
    middleware: Dict[str, Any] = field(default_factory=lambda: {
        "shell_access": True,
        "context_editing": True,
        "file_search": True,
        "human_in_loop": False,
    })
    
    # Memory settings
    memory_config: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "session_id": "coding_session",
        "max_context_tokens": 4000,
    })
    
    # RAG settings
    rag_config: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "docs_urls": [],
        "docs_files": [],
    })
    
    # CLI appearance (from Agent Forge UI)
    cli_appearance: Dict[str, Any] = field(default_factory=lambda: {
        "primary_color": "#00ff41",
        "secondary_color": "#ffffff",
        "accent_color": "#00d9ff",
        "error_color": "#ff5555",
        "warning_color": "#ffff55",
        "success_color": "#55ff55",
        "background": "dark",
        "font": "monospace",
        "show_banner": True,
        "color_scheme": "default",
    })
    
    # ASCII Art configuration (from Agent Forge CLIAppearancePanel)
    ascii_art: Dict[str, Any] = field(default_factory=lambda: {
        "font_banner": None,           # ASCII font art (e.g., figlet text)
        "font_banner_color": "#00FF00",  # Color for font banner
        "pixel_art": None,             # Pixel art with ANSI colors
        "show_pixel_art": True,        # Whether to display pixel art
        "show_font_banner": True,      # Whether to display font banner
        "banner_order": "banner-first", # 'banner-first', 'pixel-first', 'banner-only', 'pixel-only'
    })
    
    # Full color palette (all UI color settings)
    colors: Dict[str, Any] = field(default_factory=dict)
    
    # =========================================================================
    # DEFAULT PROMPT SECTIONS
    # =========================================================================
    
    DEFAULT_OPENING = "You are {agent_name}, an AI agent built with LangChain 1.0."
    
    DEFAULT_SHELL_INSTRUCTIONS = """SHELL ACCESS:
You have access to a persistent shell session via ShellToolMiddleware.
This is SEPARATE from your regular tools - it's always available but hidden.

SHELL COMMANDS (run via shell middleware):
- System info: nvidia-smi, Get-ComputerInfo, systeminfo
- File operations: dir, ls, cat, type, echo, mkdir, rm
- Run programs: python script.py, node app.js, npm start
- Package management: pip install, npm install
- Git: git status, git commit, git push
- Any PowerShell/Bash command

NOTE: Shell commands are different from your LangChain tools.
- Tools (like read_file_content, code_analyzer) are function calls
- Shell commands are system commands executed in a terminal

When using shell:
- Explain what you're doing BEFORE running commands
- Show the exact command syntax
- Report output clearly
- Session is persistent (cd, env vars maintained)
- 120-second timeout
- Be careful with destructive operations"""

    DEFAULT_CLOSING = "Be helpful, precise, and efficient in your responses."
    
    def build_system_prompt(self) -> str:
        """
        Build the complete system prompt from config sections.
        
        Combines:
        - Opening (agent introduction)
        - Core instructions (system_prompt field)
        - Shell instructions (if enabled)
        - Closing (behavioral guidance)
        
        Each section can be customized or disabled via prompt_* fields.
        """
        parts = []
        
        # Opening section
        if self.prompt_opening is not False:
            opening = self.prompt_opening if isinstance(self.prompt_opening, str) else self.DEFAULT_OPENING
            parts.append(opening.replace('{agent_name}', self.name))
        
        # Core instructions (always included if present)
        if self.system_prompt:
            parts.append(self.system_prompt)
        
        # Shell instructions (only if shell enabled and not disabled)
        if self.enable_shell and self.prompt_shell is not False:
            shell = self.prompt_shell if isinstance(self.prompt_shell, str) else self.DEFAULT_SHELL_INSTRUCTIONS
            parts.append(shell)
        
        # Closing section
        if self.prompt_closing is not False:
            closing = self.prompt_closing if isinstance(self.prompt_closing, str) else self.DEFAULT_CLOSING
            parts.append(closing)
        
        return "\n\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, filepath: str):
        """Save configuration to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        """Load from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentConfig':
        """Load from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def load(cls, filepath: str) -> 'AgentConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            return cls.from_json(f.read())


def create_agent_from_config(config: AgentConfig, **overrides):
    """
    Create an agent from configuration.
    
    This is the UNIVERSAL agent factory that works for:
    - UI exports
    - CLI usage
    - Programmatic creation
    
    Args:
        config: AgentConfig instance
        **overrides: Override any config parameters
        
    Returns:
        Configured Agent instance
    """
    from src.base import (
        Agent,
        create_ultimate_coding_agent,
        create_math_agent,
        create_science_agent,
    )
    from src.toolbox import get_toolbox
    
    # Apply overrides to config
    if overrides:
        config_dict = config.to_dict()
        config_dict.update(overrides)
        config = AgentConfig.from_dict(config_dict)
    
    params = config.to_dict()
    
    # Determine which factory function to use
    factory_map = {
        "create_ultimate_coding_agent": create_ultimate_coding_agent,
        "create_math_agent": create_math_agent,
        "create_science_agent": create_science_agent,
        "Agent": Agent,  # Generic agent
    }
    
    factory = factory_map.get(params['base_agent'], create_ultimate_coding_agent)
    
    # Build the complete system prompt from config
    system_prompt = config.build_system_prompt()
    
    # Build agent parameters
    agent_params = {
        'project_root': params.get('project_root'),
        'workspace_root': params.get('workspace_root'),
        'enable_shell': params.get('enable_shell', True),
        'enable_file_ops': params.get('enable_file_ops', True),
        'enable_memory': params.get('enable_memory', True),
        'enable_rag': params.get('enable_rag', False),
        'enable_commands': params.get('enable_commands', True),
        'session_id': params.get('memory_config', {}).get('session_id', 'session'),
        'system_prompt': system_prompt,  # Use the built system prompt
    }
    
    # Remove None values (but keep empty strings)
    agent_params = {k: v for k, v in agent_params.items() if v is not None}
    
    # Create agent
    agent = factory(**agent_params)
    
    # Load toolboxes
    toolbox = get_toolbox()
    for toolbox_name in params.get('toolboxes', []):
        try:
            tools = toolbox.get_tools_by_category(toolbox_name)
            if tools:
                agent.add_tools(tools)
        except Exception as e:
            print(f"Warning: Could not load toolbox '{toolbox_name}': {e}")
    
    # Add custom tools
    for tool_data in params.get('custom_tools', []):
        try:
            if 'code' in tool_data:
                success, msg, tool = toolbox.add_tool_from_code(
                    tool_data['code'],
                    category=tool_data.get('category', 'custom'),
                    author=tool_data.get('author', 'user'),
                )
                if success and tool:
                    agent.add_tool(tool)
        except Exception as e:
            print(f"Warning: Could not add custom tool: {e}")
    
    return agent


# ============================================================================
# EXAMPLE CONFIGURATIONS
# ============================================================================

CORE_CODER_V3_CONFIG = AgentConfig(
    name="Core Coder v3",
    version="3.0.0",
    description="Ultimate coding agent with shell access and memory",
    category="coding",
    base_agent="create_ultimate_coding_agent",
    enable_shell=True,
    enable_file_ops=True,
    enable_memory=True,
    enable_rag=False,
    enable_commands=True,
    toolboxes=["coding", "math"],
    
    # System prompt customization
    system_prompt="""A senior full-stack developer with deep expertise in Python, JavaScript, and modern frameworks.

Your expertise includes:
- Backend: Python, FastAPI, Django, Node.js, Express
- Frontend: React, Vue, TypeScript, CSS/Tailwind
- DevOps: Docker, CI/CD, cloud deployment
- Databases: PostgreSQL, MongoDB, Redis

When coding:
- Write clean, well-documented code
- Follow best practices and design patterns
- Consider security and performance implications
- Test thoroughly before committing""",
    
    # Use defaults for opening, shell, and closing (None = default)
    prompt_opening=None,  # Uses: "You are Core Coder v3, an AI agent built with LangChain 1.0."
    prompt_shell=None,    # Uses default shell instructions
    prompt_closing=None,  # Uses: "Be helpful, precise, and efficient in your responses."
    
    middleware={
        "shell_access": True,
        "context_editing": True,
        "file_search": True,
        "human_in_loop": False,
    },
    memory_config={
        "enabled": True,
        "session_id": "core_coder_v3_session",
        "max_context_tokens": 8000,
    },
    cli_appearance={
        "primary_color": "#00ff41",
        "secondary_color": "#ffffff",
        "background": "dark",
        "font": "Fira Code",
        "show_banner": True,
    }
)


# Example: Customized opening and disabled closing
DEVOPS_AGENT_CONFIG = AgentConfig(
    name="DevOps Commander",
    version="1.0.0",
    description="Infrastructure automation and deployment specialist",
    category="devops",
    base_agent="create_ultimate_coding_agent",
    enable_shell=True,
    enable_file_ops=True,
    enable_memory=False,
    toolboxes=["coding"],
    
    system_prompt="""A DevOps engineer focused on infrastructure, automation, and reliability.

Your expertise includes:
- CI/CD pipeline design and optimization
- Cloud infrastructure (AWS, Azure, GCP)
- Container orchestration (Docker, Kubernetes)
- Infrastructure as Code (Terraform, Ansible)
- Monitoring and observability (Prometheus, Grafana)

Always prioritize:
- Security best practices
- Cost optimization
- High availability
- Documentation""",
    
    # Custom opening
    prompt_opening="You are {agent_name}, a battle-tested DevOps engineer ready to automate everything.",
    
    # Custom shell instructions (shorter)
    prompt_shell="""SHELL ACCESS:
You have full shell access. Use it for:
- Infrastructure commands (terraform, kubectl, docker)
- System diagnostics (df, top, netstat)
- Deployment scripts and automation
Always show commands before running. Be careful with production systems.""",
    
    # Disable closing (False = don't add)
    prompt_closing=False,
)


CLI_CODING_MASTER_CONFIG = AgentConfig(
    name="CLI Coding Master",
    version="1.0.0",
    description="90% coding via CLI, 10% API",
    category="coding",
    base_agent="create_ultimate_coding_agent",
    enable_shell=True,
    enable_file_ops=True,
    enable_memory=False,  # Disabled by default (requires Qdrant)
    enable_rag=False,
    enable_commands=True,
    toolboxes=["coding"],
    middleware={
        "shell_access": True,
        "context_editing": False,
        "file_search": True,
        "human_in_loop": False,
    },
)


def save_example_configs():
    """Save example configurations."""
    
    # Core Coder v3 (what UI exports)
    CORE_CODER_V3_CONFIG.save("configs/core_coder_v3.json")
    
    # CLI Coding Master (what cli_coding_agent.py uses)
    CLI_CODING_MASTER_CONFIG.save("configs/cli_coding_master.json")
    
    print("✅ Example configurations saved:")
    print("  - configs/core_coder_v3.json")
    print("  - configs/cli_coding_master.json")


if __name__ == "__main__":
    # Save examples
    save_example_configs()
    
    # Demonstrate loading and creating agent
    print("\n🎯 Demonstrating configuration system:")
    
    # Load config
    config = AgentConfig.load("configs/core_coder_v3.json")
    print(f"\nLoaded config: {config.name} v{config.version}")
    print(f"  Base agent: {config.base_agent}")
    print(f"  Toolboxes: {', '.join(config.toolboxes)}")
    print(f"  Shell access: {config.enable_shell}")
    print(f"  Memory: {config.enable_memory}")
    
    # Create agent from config
    print("\n🚀 Creating agent from config...")
    try:
        agent = create_agent_from_config(config)
        print(f"✅ Agent created with {len(agent.list_tools())} tools")
        print(f"✅ Commands available: {len(agent.list_commands())}")
    except Exception as e:
        print(f"Note: {e}")
        print("(This is expected if dependencies aren't fully installed)")
