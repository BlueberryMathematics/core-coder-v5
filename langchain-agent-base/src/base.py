"""
LangChain Agent Base Classes
============================

A comprehensive, production-ready system for building LangChain agents with Groq's gpt-oss-120b model.
Designed for coding, math, science, and general applications with advanced tool, RAG, middleware, 
and memory integration.

🎯 NEW: Ultimate Coding Agent Capabilities
- Comprehensive file operations (read, write, search, analyze) with security boundaries
- Shell command execution via persistent middleware sessions
- Advanced code analysis, syntax checking, and quality assessment
- Project structure creation and git integration
- Conversation memory for context-aware development
- RAG integration for documentation search
- Rich command interface for direct operations
- Dynamic tool generation and management

🚀 Quick Start - Ultimate Coding Agent:
    from .base import create_ultimate_coding_agent
    
    agent = create_ultimate_coding_agent(
        project_root="/my-project",
        enable_shell=True,
        enable_memory=True,
        session_id="my_coding_session"
    )
    
    response = agent.chat(\"\"\"
    Please help me:
    1. Analyze the project structure
    2. Read the main.py file and suggest improvements
    3. Run the tests and fix any issues
    \"\"\")
    
    # Direct command usage
    agent.execute_command("ls")
    agent.execute_command("find", pattern="*.py")
    agent.execute_command("git", command="status")

📚 RAG-Enhanced Agent:
    from .base import create_rag_enhanced_coding_agent
    
    agent = await create_rag_enhanced_coding_agent(
        project_root="/my-project",
        docs_urls=["https://docs.python.org/3/"],
        docs_files=["./README.md"]
    )

🔧 Custom Configuration:
    from .base import Agent
    from .tools import get_coding_tools
    
    agent = Agent(
        enable_context_editing=True,
        enable_shell_tool=True,
        workspace_root="/workspace",
        enable_file_search=True,
        enable_memory=True
    )
    
    agent.add_tools(get_coding_tools())
    agent.generate_and_add_tool("Custom coding tool", category="coding")
"""

import os
import asyncio
from typing import List, Optional, Dict, Any, Callable

from langchain_groq import ChatGroq
try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

from langchain.agents import create_agent
from langchain_core.tools import tool, Tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

try:
    from langchain.agents.middleware import (
        HumanInTheLoopMiddleware,
        ContextEditingMiddleware,
        ClearToolUsesEdit,
        ShellToolMiddleware,
        HostExecutionPolicy,
        DockerExecutionPolicy,
        FilesystemFileSearchMiddleware
    )
except ImportError:
    HumanInTheLoopMiddleware = None
    ContextEditingMiddleware = None
    ClearToolUsesEdit = None
    ShellToolMiddleware = None
    HostExecutionPolicy = None
    DockerExecutionPolicy = None
    FilesystemFileSearchMiddleware = None

from tools import get_basic_tools, get_math_tools, get_science_tools, get_coding_tools
from rag import setup_rag_tools
from commands import CommandRegistry, create_math_commands, create_science_commands, create_coding_commands, create_agent_commands

try:
    from toolbox import get_toolbox, ToolboxManager
    from tool_generator import ToolGenerator, ToolAssistant
    TOOLBOX_AVAILABLE = True
except ImportError:
    TOOLBOX_AVAILABLE = False

try:
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False


class Agent:
    """
    A flexible agent class that can be configured with any tools and capabilities.
    This follows the original simple design pattern from agent.py.
    """
    
    def __init__(self, 
                 model_name: str = "openai/gpt-oss-120b",
                 provider: str = "groq",
                 temperature: float = 0,
                 system_prompt: str = "You are a helpful AI assistant specialized in coding, math, and science.",
                 tools: List[Callable] = None,
                 enable_commands: bool = False,
                 enable_memory: bool = False,
                 memory_session_id: str = "default",
                 # Middleware options
                 enable_context_editing: bool = False,
                 context_token_trigger: int = 100000,
                 context_keep_results: int = 3,
                 enable_shell_tool: bool = False,
                 workspace_root: str = None,
                 shell_execution_policy: str = "host",  # "host" or "docker"
                 shell_startup_commands: List[str] = None,  # NEW: startup commands for shell
                 shell_timeout: int = 120,  # Shell command timeout in seconds (default: 120s)
                 enable_file_search: bool = False,
                 file_search_root: str = None,
                 use_ripgrep: bool = True,
                 **model_kwargs):
        """
        Initialize the agent.
        
        Args:
            model_name: The model to use
            provider: The LLM provider ("groq" or "ollama")
            temperature: Model temperature (0-2)
            system_prompt: System prompt for the agent
            tools: Initial list of tools to add
            enable_commands: Whether to enable command system
            **model_kwargs: Additional model parameters
        """
        self.model_name = model_name
        self.provider = provider
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.model_kwargs = model_kwargs
        self.tools = []
        self.agent = None
        
        # Initialize command system if requested
        self.commands = CommandRegistry() if enable_commands else None
        
        # Memory system integration
        self.enable_memory = enable_memory
        self.memory_session_id = memory_session_id
        self.memory_manager = None
        
        if enable_memory and MEMORY_AVAILABLE:
            try:
                from .memory import get_memory_manager
                self.memory_manager = get_memory_manager()
            except ImportError:
                print("WARNING: Memory system not available")
                self.memory_manager = None
        
        # Middleware configuration
        self.enable_context_editing = enable_context_editing
        self.context_token_trigger = context_token_trigger
        self.context_keep_results = context_keep_results
        self.enable_shell_tool = enable_shell_tool
        self.workspace_root = workspace_root or os.getcwd()
        self.shell_execution_policy = shell_execution_policy
        self.shell_startup_commands = shell_startup_commands or []  # NEW: store startup commands
        self.shell_timeout = shell_timeout  # Shell command timeout
        self.enable_file_search = enable_file_search
        self.file_search_root = file_search_root or self.workspace_root
        self.use_ripgrep = use_ripgrep
        
        # Setup model
        if self.provider == "ollama":
            if ChatOllama is None:
                raise ImportError("langchain-ollama is not installed. Please install it with: pip install langchain-ollama")
            
            self.model = ChatOllama(
                model=self.model_name,
                temperature=self.temperature,
                **self.model_kwargs
            )
        else:
            # Default to Groq
            self.model = ChatGroq(
                model=self.model_name,
                temperature=self.temperature,
                **self.model_kwargs
            )
        
        # Add initial tools
        if tools:
            self.add_tools(tools)
        else:
            # Add basic tools by default
            self.add_tools(get_basic_tools())
    
    def add_tool(self, tool_func: Callable):
        """
        Add a tool to the agent.
        
        Args:
            tool_func: A function decorated with @tool or a Tool object
        """
        self.tools.append(tool_func)
        self._rebuild_agent()
    
    def add_tools(self, tools: List[Callable]):
        """Add multiple tools at once."""
        self.tools.extend(tools)
        self._rebuild_agent()
    
    def remove_tool(self, tool_name: str):
        """Remove a tool by name."""
        self.tools = [t for t in self.tools if getattr(t, 'name', str(t)) != tool_name]
        self._rebuild_agent()
    
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return [getattr(tool, 'name', str(tool)) for tool in self.tools]
    
    def get_tools(self) -> List[Callable]:
        """Get all tool objects."""
        return self.tools.copy()
    
    def load_tools_from_toolbox(self, category: str = None, tags: List[str] = None):
        """
        Load tools from the toolbox system.
        
        Args:
            category: Load tools from specific category
            tags: Load tools matching specific tags
        """
        if not TOOLBOX_AVAILABLE:
            print("WARNING: Toolbox system not available")
            return
        
        toolbox = get_toolbox()
        
        if category:
            tools = toolbox.get_tools_by_category(category)
        elif tags:
            tools = toolbox.get_tools_by_tags(tags)
        else:
            tools = toolbox.get_all_tools()
        
        self.add_tools(tools)
        print(f"✅ Loaded {len(tools)} tools from toolbox")
    
    def generate_and_add_tool(self, description: str, category: str = "custom") -> bool:
        """
        Generate a new tool using LLM and add it to the agent.
        
        Args:
            description: What the tool should do
            category: Tool category
        
        Returns:
            True if successful
        """
        if not TOOLBOX_AVAILABLE:
            print("WARNING: Tool generator not available")
            return False
        
        assistant = ToolAssistant()
        success, message, tool_func = assistant.create_tool_for_agent(
            self,
            tool_description=description,
            category=category,
            add_to_agent=True
        )
        
        print(message)
        return success
    
    def _add_windows_shell_tool(self):
        """Add a cross-platform shell tool that works on Windows, Linux, and macOS.
        
        The ShellToolMiddleware has issues on Windows with persistent sessions.
        This provides a simpler, reliable alternative using subprocess.
        
        Platform detection:
        - Windows: Uses PowerShell (pwsh or powershell.exe)
        - Linux/macOS: Uses bash or sh
        """
        import subprocess
        import shutil
        import platform
        
        is_windows = platform.system() == "Windows"
        
        # Determine shell to use based on platform
        if is_windows:
            # Prefer PowerShell 7 (pwsh), fall back to Windows PowerShell
            shell_cmd = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            shell_args = ["-NoProfile", "-NoLogo", "-Command"]
        else:
            # Linux/macOS: Use bash or sh
            shell_cmd = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
            shell_args = ["-c"]
        
        timeout = self.shell_timeout
        workspace = self.workspace_root or "."
        
        @tool
        def run_powershell_command(command: str) -> str:
            """Execute a shell command and return the COMPLETE output.
            
            On Windows: Uses PowerShell (pwsh or powershell.exe)
            On Linux/macOS: Uses bash or sh
            
            Use this tool to run system commands like:
            - File operations: ls, dir, cat, cp, mv, rm, mkdir
            - System info: uname, hostname, whoami, ps, top
            - Network: ifconfig, ip, ping, netstat, curl
            - Development: python, pip, git, npm, node
            - GPU/Hardware: nvidia-smi, lspci, lsblk
            
            Args:
                command: The shell command to execute
                
            Returns:
                COMPLETE command output (stdout + stderr) without truncation
            """
            try:
                # Build command args based on platform
                cmd_list = [shell_cmd] + shell_args + [command]
                
                # Run command with proper encoding for unicode support
                result = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    timeout=timeout,
                    cwd=workspace,
                    shell=False,
                    # Use proper encoding for Windows
                    encoding='utf-8',
                    errors='replace'  # Replace undecodable chars instead of failing
                )
                
                # Combine stdout and stderr
                output_parts = []
                if result.stdout:
                    output_parts.append(result.stdout)
                if result.stderr:
                    output_parts.append(result.stderr)
                
                output = "\n".join(output_parts) if output_parts else ""
                
                if not output.strip():
                    output = f"(no output - exit code {result.returncode})"
                
                # Return FULL output with clear formatting
                # The entire output is returned - no truncation
                full_output = f"$ {command}\n{output.strip()}"
                
                # Add exit code if non-zero for debugging
                if result.returncode != 0:
                    full_output += f"\n\n[Exit code: {result.returncode}]"
                
                return full_output
                
            except subprocess.TimeoutExpired:
                return f"$ {command}\n\n[ERROR] Command timed out after {timeout} seconds.\nConsider increasing shell_timeout if the command needs more time."
            except FileNotFoundError:
                return f"$ {command}\n\n[ERROR] Shell not found: {shell_cmd}\nPlease ensure PowerShell (Windows) or bash (Linux/macOS) is installed."
            except Exception as e:
                return f"$ {command}\n\n[ERROR] Failed to execute command: {str(e)}"
        
        # Add directly to self.tools to avoid rebuild recursion
        self.tools.append(run_powershell_command)
    
    def _rebuild_agent(self):
        """Rebuild the agent with current tools and configuration."""
        middleware = self._build_middleware()
        
        # Only pass middleware if we have any
        agent_kwargs = {
            "model": self.model,
            "tools": self.tools,
            "system_prompt": self.system_prompt
        }
        
        if middleware:  # Only add middleware if we have any
            agent_kwargs["middleware"] = middleware
        
        self.agent = create_agent(**agent_kwargs)
    
    def _build_middleware(self) -> List[Any]:
        """Build middleware list based on configuration."""
        middleware = []
        
        # Context editing middleware
        if (self.enable_context_editing and 
            ContextEditingMiddleware is not None and 
            ClearToolUsesEdit is not None):
            try:
                middleware.append(
                    ContextEditingMiddleware(
                        edits=[
                            ClearToolUsesEdit(
                                trigger=self.context_token_trigger,
                                keep=self.context_keep_results,
                            ),
                        ],
                    )
                )
            except Exception as e:
                print(f"WARNING: Failed to create ContextEditingMiddleware: {e}")
        
        # Shell tool middleware with startup commands support
        # NOTE: ShellToolMiddleware works best on Linux. On Windows, we use a simple subprocess tool.
        import platform
        
        if self.enable_shell_tool:
            if platform.system() == "Windows":
                # Windows: Use simple subprocess-based tool (middleware has issues with Windows)
                self._add_windows_shell_tool()
                print(f"✓ Windows shell tool added (subprocess-based, timeout: {self.shell_timeout}s)")
            elif ShellToolMiddleware is not None:
                # Linux/Mac: Use the proper middleware
                try:
                    if self.shell_execution_policy == "docker" and DockerExecutionPolicy is not None:
                        execution_policy = DockerExecutionPolicy(command_timeout=self.shell_timeout)
                        print(f"✓ Docker execution policy with timeout: {self.shell_timeout}s")
                    elif HostExecutionPolicy is not None:
                        execution_policy = HostExecutionPolicy(command_timeout=self.shell_timeout)
                        print(f"✓ Host execution policy with command_timeout: {self.shell_timeout}s")
                    else:
                        execution_policy = None
                    
                    if execution_policy:
                        shell_config = {
                            "workspace_root": self.workspace_root,
                            "execution_policy": execution_policy,
                        }
                        
                        if self.shell_startup_commands:
                            shell_config["startup_commands"] = self.shell_startup_commands
                        
                        middleware.append(ShellToolMiddleware(**shell_config))
                        print(f"✓ Shell middleware added successfully")
                    else:
                        print("WARNING: Shell middleware enabled but no execution policy available")
                except Exception as e:
                    print(f"WARNING: Failed to create ShellToolMiddleware: {e}")
                    print("         Agent will work without shell capabilities")
                    import traceback
                    traceback.print_exc()
        
        # File search middleware
        if (self.enable_file_search and 
            FilesystemFileSearchMiddleware is not None):
            try:
                middleware.append(
                    FilesystemFileSearchMiddleware(
                        root_path=self.file_search_root,
                        use_ripgrep=self.use_ripgrep,
                    )
                )
            except Exception as e:
                print(f"WARNING: Failed to create FilesystemFileSearchMiddleware: {e}")
        
        return middleware

    def chat(self, message: str, session_id: str = None, **kwargs) -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            message: The user message
            session_id: Optional session ID for memory (overrides default)
            **kwargs: Additional parameters for the agent
        
        Returns:
            The agent's response as a string
        """
        if not self.agent:
            self._rebuild_agent()
        
        # Handle memory integration
        if self.enable_memory and self.memory_manager:
            actual_session_id = session_id or self.memory_session_id
            
            # Get conversation context
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                context = loop.run_until_complete(
                    self.memory_manager.get_context_for_session(actual_session_id)
                )
                
                # Enhance message with context
                if context:
                    enhanced_message = f"""Previous conversation context:
{context}

Current message: {message}"""
                else:
                    enhanced_message = message
                
                # Get response
                # Extract callbacks from kwargs and put in config
                callbacks = kwargs.pop('callbacks', None)
                config = kwargs.pop('config', {})
                if callbacks:
                    config['callbacks'] = callbacks
                
                response = self.agent.invoke({
                    "messages": [{"role": "user", "content": enhanced_message}]
                }, config=config if config else None)
                
                response_content = response["messages"][-1].content
                
                # Store in memory
                loop.run_until_complete(
                    self.memory_manager.add_message(
                        session_id=actual_session_id,
                        message=message,  # Store original message, not enhanced
                        response=response_content
                    )
                )
                
                return response_content
                
            finally:
                loop.close()
        else:
            # Standard chat without memory
            # Extract callbacks from kwargs and put in config
            callbacks = kwargs.pop('callbacks', None)
            config = kwargs.pop('config', {})
            if callbacks:
                config['callbacks'] = callbacks
            
            response = self.agent.invoke({
                "messages": [{"role": "user", "content": message}]
            }, config=config if config else None)
            
            return response["messages"][-1].content
    
    def stream_chat(self, message: str, **kwargs):
        """
        Stream the agent's response.
        
        Args:
            message: The user message
            **kwargs: Additional parameters for the agent
        
        Yields:
            Chunks of the agent's response
        """
        if not self.agent:
            self._rebuild_agent()
        
        for chunk in self.agent.stream({
            "messages": [{"role": "user", "content": message}]
        }, **kwargs):
            if "messages" in chunk:
                yield chunk["messages"][-1].content
    
    def chat_with_tool_display(self, message: str, session_id: str = None, 
                                tool_callback=None, **kwargs) -> dict:
        """
        Send a message and capture all tool calls with their outputs.
        
        This method returns both the final response AND all tool invocations
        that occurred, allowing the CLI to display tool outputs directly.
        
        Args:
            message: The user message
            session_id: Optional session ID for memory
            tool_callback: Optional callback function(tool_name, tool_input, tool_output)
                          called when each tool completes. Use for real-time display.
            **kwargs: Additional parameters for the agent
        
        Returns:
            dict with:
                - 'response': The final agent response string
                - 'tool_calls': List of dicts with 'name', 'input', 'output' for each tool
        """
        if not self.agent:
            self._rebuild_agent()
        
        tool_calls = []
        
        # Handle memory context enhancement
        if self.enable_memory and self.memory_manager:
            actual_session_id = session_id or self.memory_session_id
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                context = loop.run_until_complete(
                    self.memory_manager.get_context_for_session(actual_session_id)
                )
                if context:
                    enhanced_message = f"""Previous conversation context:
{context}

Current message: {message}"""
                else:
                    enhanced_message = message
            finally:
                loop.close()
        else:
            enhanced_message = message
            actual_session_id = session_id
        
        # Use stream to capture tool calls as they happen
        final_response = None
        
        # Extract callbacks from kwargs and put in config
        callbacks = kwargs.pop('callbacks', None)
        config = kwargs.pop('config', {})
        if callbacks:
            config['callbacks'] = callbacks
        
        for event in self.agent.stream({
            "messages": [{"role": "user", "content": enhanced_message}]
        }, stream_mode="updates", config=config if config else None):
            # The stream yields updates - look for tool messages and AI messages
            if "messages" in event:
                for msg in event["messages"]:
                    # Check message type
                    msg_type = type(msg).__name__
                    
                    # ToolMessage contains the tool output
                    if msg_type == "ToolMessage":
                        tool_info = {
                            "name": getattr(msg, 'name', 'unknown_tool'),
                            "input": getattr(msg, 'tool_call_id', ''),
                            "output": msg.content
                        }
                        tool_calls.append(tool_info)
                        
                        # Call the callback for real-time display
                        if tool_callback:
                            tool_callback(tool_info["name"], tool_info["input"], tool_info["output"])
                    
                    # AIMessage with content is the final response
                    elif msg_type == "AIMessage":
                        if hasattr(msg, 'content') and msg.content:
                            final_response = msg.content
                        
                        # Also capture tool calls from AIMessage
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tc in msg.tool_calls:
                                # This is the tool being called (before output)
                                pass  # We'll get the output from ToolMessage
        
        # If stream didn't work as expected, fall back to invoke
        if final_response is None:
            response = self.agent.invoke({
                "messages": [{"role": "user", "content": enhanced_message}]
            }, **kwargs)
            
            # Parse messages for tool calls
            for msg in response.get("messages", []):
                msg_type = type(msg).__name__
                if msg_type == "ToolMessage":
                    tool_info = {
                        "name": getattr(msg, 'name', 'unknown_tool'),
                        "input": "",
                        "output": msg.content
                    }
                    tool_calls.append(tool_info)
                    if tool_callback:
                        tool_callback(tool_info["name"], "", tool_info["output"])
                elif msg_type == "AIMessage" and hasattr(msg, 'content') and msg.content:
                    final_response = msg.content
        
        # Store in memory if enabled
        if self.enable_memory and self.memory_manager and actual_session_id:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.memory_manager.add_message(
                        session_id=actual_session_id,
                        message=message,
                        response=final_response or ""
                    )
                )
            finally:
                loop.close()
        
        return {
            "response": final_response or "",
            "tool_calls": tool_calls
        }
    
    def enable_commands(self):
        """Enable the command system for this agent."""
        if not self.commands:
            self.commands = CommandRegistry()
    
    def enable_middleware_context_editing(self, token_trigger: int = 100000, keep_results: int = 3):
        """Enable context editing middleware."""
        self.enable_context_editing = True
        self.context_token_trigger = token_trigger
        self.context_keep_results = keep_results
        self._rebuild_agent()
    
    def enable_middleware_shell_tool(self, workspace_root: str = None, execution_policy: str = "host"):
        """Enable shell tool middleware."""
        self.enable_shell_tool = True
        if workspace_root:
            self.workspace_root = workspace_root
        self.shell_execution_policy = execution_policy
        self._rebuild_agent()
    
    def enable_middleware_file_search(self, search_root: str = None, use_ripgrep: bool = True):
        """Enable file search middleware."""
        self.enable_file_search = True
        if search_root:
            self.file_search_root = search_root
        self.use_ripgrep = use_ripgrep
        self._rebuild_agent()
    
    def disable_middleware_context_editing(self):
        """Disable context editing middleware."""
        self.enable_context_editing = False
        self._rebuild_agent()
    
    def disable_middleware_shell_tool(self):
        """Disable shell tool middleware."""
        self.enable_shell_tool = False
        self._rebuild_agent()
    
    def disable_middleware_file_search(self):
        """Disable file search middleware."""
        self.enable_file_search = False
        self._rebuild_agent()
    
    def get_middleware_status(self) -> Dict[str, Any]:
        """Get current middleware configuration."""
        return {
            "context_editing": {
                "enabled": self.enable_context_editing,
                "token_trigger": self.context_token_trigger,
                "keep_results": self.context_keep_results
            },
            "shell_tool": {
                "enabled": self.enable_shell_tool,
                "workspace_root": self.workspace_root,
                "execution_policy": self.shell_execution_policy
            },
            "file_search": {
                "enabled": self.enable_file_search,
                "search_root": self.file_search_root,
                "use_ripgrep": self.use_ripgrep
            }
        }
    
    def add_command(self, command_func: Callable):
        """
        Add a command to the agent.
        
        Args:
            command_func: Function decorated with @command
        """
        if not self.commands:
            self.enable_commands()
        self.commands.add_command(command_func)
    
    def add_commands(self, command_funcs: List[Callable]):
        """
        Add multiple commands to the agent.
        
        Args:
            command_funcs: List of functions decorated with @command
        """
        for cmd in command_funcs:
            self.add_command(cmd)
    
    def execute_command(self, command: str, **kwargs) -> str:
        """
        Execute a command directly.
        
        Args:
            command: Command to execute (with or without /)
            **kwargs: Command arguments
            
        Returns:
            Command result
        """
        if not self.commands:
            return "Commands not enabled. Call enable_commands() first."
        
        return self.commands.execute_command(command, **kwargs)
    
    def list_commands(self) -> List[str]:
        """List all available commands."""
        if not self.commands:
            return []
        return self.commands.list_command_names()
    
    def get_command_help(self, command_name: str) -> str:
        """Get help for a specific command."""
        if not self.commands:
            return "Commands not enabled."
        return self.execute_command("help", command_name=command_name)


# ============================================================================
# FACTORY FUNCTIONS - Convenience functions for creating specialized agents
# ============================================================================

def create_simple_agent(**kwargs) -> Agent:
    """
    Create a basic agent with default tools.
    
    Usage:
        agent = create_simple_agent()
        agent.add_tools(get_coding_tools())
    """
    return Agent(**kwargs)


async def create_rag_agent(urls: List[str] = None, documents: List[str] = None, **kwargs) -> Agent:
    """
    Create an agent with RAG capabilities.
    
    Args:
        urls: URLs to documentation to ingest
        documents: Local documents to ingest
        **kwargs: Additional agent configuration
    
    Usage:
        agent = await create_rag_agent(
            urls=["https://docs.python.org/3/"],
            documents=["./README.md"]
        )
    """
    agent = Agent(**kwargs)
    
    # Add RAG tools to the agent
    try:
        if urls or documents:
            from .rag import RAGManager
            rag_manager = RAGManager()
            
            if urls:
                rag_tools = await rag_manager.setup_from_urls(urls, "documents")
            else:
                rag_tools = await rag_manager.setup_from_documents(documents, "documents")
            
            agent.add_tools(rag_tools)
        else:
            rag_tools = await setup_rag_tools()
            agent.add_tools(rag_tools)
    except Exception as e:
        print(f"Failed to setup RAG tools: {e}")
    
    agent.system_prompt += " Use the search tools to find relevant information before answering questions."
    agent._rebuild_agent()
    
    return agent


def create_ultimate_coding_agent(
    project_root: str = None,
    workspace_root: str = None,
    enable_shell: bool = True,
    enable_file_ops: bool = True,
    enable_memory: bool = True,
    enable_rag: bool = False,
    enable_commands: bool = True,
    session_id: str = "coding_session",
    system_prompt: str = None,
    **kwargs
) -> Agent:
    """
    Create the ultimate coding agent with comprehensive development capabilities.
    
    This agent combines all the best features:
    - File operations (read, write, search, analyze)
    - Shell command execution via middleware
    - Code analysis and syntax checking  
    - Project structure creation
    - Git operations
    - Memory for conversation context
    - Optional RAG for documentation
    - Rich command interface
    
    Args:
        project_root: Root directory for file operations (security boundary)
        workspace_root: Workspace directory for shell operations
        enable_shell: Enable shell tool middleware
        enable_file_ops: Enable file operation tools
        enable_memory: Enable conversation memory
        enable_rag: Enable RAG capabilities
        enable_commands: Enable command interface
        session_id: Session ID for memory management
        system_prompt: Custom system prompt (overrides default). Use AgentConfig.build_system_prompt() for best results.
        **kwargs: Additional agent configuration
    """
    
    # Determine workspace boundaries
    actual_workspace = workspace_root or project_root or os.getcwd()
    
    # Build comprehensive tool set
    tools = []
    
    if enable_file_ops:
        tools.extend(get_coding_tools())
    
    # Add basic tools for general functionality
    tools.extend(get_basic_tools())
    
    # Use custom system prompt if provided, otherwise use default
    if system_prompt is None:
        system_prompt = f"""You are an elite software development assistant with comprehensive coding capabilities.

CORE CAPABILITIES:
- File Operations: Read, write, search, and analyze files within the project directory
- Shell Access: Execute commands via persistent shell sessions (when enabled)
- Code Analysis: Syntax checking, complexity analysis, and quality assessment
- Project Management: Create project structures, git operations, development workflows
- Memory: Remember context across conversations for better assistance
- Safety: All operations are constrained to the project workspace for security

SHELL ACCESS:
You have access to a persistent shell session (ShellToolMiddleware).
This tool is ALWAYS available but NOT visible in your tools list.

You can execute shell commands to:
- Check system info (nvidia-smi, Get-ComputerInfo, systeminfo)
- Create/read/modify files (dir, cat, type, echo)
- Run scripts and programs (python script.py, node app.js)
- Install packages (pip install, npm install)
- Perform git operations (git status, git commit, git push)
- Any PowerShell or system command

IMPORTANT:
- Always explain what you're doing BEFORE running commands
- Show the exact command you're about to execute
- Report the command output clearly
- The shell session is persistent (environment variables and working directory maintained)
- Commands have a 120-second timeout
- Be careful with destructive operations

DEVELOPMENT WORKFLOW:
1. Start by understanding the project structure using file exploration tools
2. Read relevant files to understand context before making changes
3. Use code analysis tools to assess quality and identify issues
4. Make targeted changes with proper error handling
5. Test and validate changes when possible
6. Document important decisions and changes

AVAILABLE TOOLS:
- File Operations: read_file_content, write_file_content, list_directory_contents
- Search: search_files (by name), search_in_files (grep-like content search)
- Analysis: code_analyzer, syntax_checker, get_file_info
- Project: create_project_structure, git_helper
- Utilities: regex_helper, json_formatter
- Shell: Persistent shell session (middleware-level, always available when enabled)

SECURITY BOUNDARIES:
- File operations restricted to: {actual_workspace}
- Shell operations (if enabled) restricted to workspace
- No access to system files outside project directory

BEST PRACTICES:
- Always explain commands before running them
- Show exact command syntax to user
- Check if files exist before reading
- Back up important files before major changes
- Use syntax checkers before writing code
- Test changes incrementally
- Ask for confirmation on destructive operations
"""

    # Enhanced middleware configuration
    agent_config = {
        'system_prompt': system_prompt,
        'tools': tools,
        'enable_commands': enable_commands,
        'enable_memory': enable_memory,
        'memory_session_id': session_id,
        
        # File search middleware for enhanced file discovery
        'enable_file_search': True,
        'file_search_root': actual_workspace,
        'use_ripgrep': True,
        
        # Context management for long coding sessions
        'enable_context_editing': True,
        'context_token_trigger': 40000,  # Lower trigger for coding
        'context_keep_results': 8,       # Keep more results for context
        
        # Shell middleware for development commands
        'enable_shell_tool': enable_shell,
        'workspace_root': actual_workspace,
        'shell_execution_policy': 'host',  # Use host execution for development
        
        **kwargs  # User overrides
    }
    
    agent = Agent(**agent_config)
    
    # Add comprehensive coding commands
    if enable_commands:
        agent.add_commands(create_coding_commands())
        agent.add_commands(create_agent_commands())
    
    return agent


async def create_rag_enhanced_coding_agent(
    project_root: str = None,
    docs_urls: List[str] = None,
    docs_files: List[str] = None,
    **kwargs
) -> Agent:
    """
    Create a coding agent enhanced with RAG capabilities for documentation.
    
    Args:
        project_root: Project directory
        docs_urls: URLs to documentation to ingest
        docs_files: Local documentation files to ingest
        **kwargs: Additional agent configuration
        
    Usage:
        agent = await create_rag_enhanced_coding_agent(
            project_root="/my-project",
            docs_urls=["https://docs.python.org/3/"]
        )
    """
    # Create base coding agent
    agent = create_ultimate_coding_agent(
        project_root=project_root,
        enable_rag=True,
        **kwargs
    )
    
    # Add RAG tools if documentation provided
    if docs_urls or docs_files:
        try:
            from .rag import RAGManager
            rag_manager = RAGManager()
            
            if docs_urls:
                rag_tools = await rag_manager.setup_from_urls(docs_urls, "project_docs")
                agent.add_tools(rag_tools)
                
            if docs_files:
                rag_tools = await rag_manager.setup_from_documents(docs_files, "local_docs")
                agent.add_tools(rag_tools)
            
            agent.system_prompt += """

DOCUMENTATION SEARCH:
- Use the document search tools to find relevant information from ingested documentation
- Reference official docs, API documentation, and project guidelines
- Provide accurate, up-to-date information from authoritative sources
"""
            agent._rebuild_agent()
            
        except Exception as e:
            print(f"Warning: Failed to setup RAG capabilities: {e}")
    
    return agent


def create_math_agent(enable_commands: bool = True, **kwargs) -> Agent:
    """
    Create an agent specialized for mathematical tasks.
    
    Usage:
        math_agent = create_math_agent()
        result = math_agent.chat("Solve x^2 + 5x + 6 = 0")
    """
    tools = get_math_tools()
    
    agent = Agent(
        system_prompt="You are a mathematical expert. Solve complex equations, perform calculations, and explain mathematical concepts clearly.",
        tools=tools,
        enable_commands=enable_commands,
        **kwargs
    )
    
    if enable_commands:
        agent.add_commands(create_math_commands())
        agent.add_commands(create_agent_commands())
    
    return agent


def create_science_agent(enable_commands: bool = True, **kwargs) -> Agent:
    """
    Create an agent specialized for scientific tasks.
    
    Usage:
        science_agent = create_science_agent()
        result = science_agent.chat("Convert 100 pounds to kilograms")
    """
    tools = get_science_tools()
    
    agent = Agent(
        system_prompt="You are a scientific expert. Help with physics, chemistry, biology, and other scientific calculations and concepts.",
        tools=tools,
        enable_commands=enable_commands,
        **kwargs
    )
    
    if enable_commands:
        agent.add_commands(create_science_commands())
        agent.add_commands(create_agent_commands())
    
    return agent
