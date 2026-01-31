"""
API Server for Core Coder V5
============================

Run this to expose your CLI agent to Next.js frontend via FastAPI + WebSocket.

Usage:
    python api_server.py

This starts a server on http://localhost:8000 with:
- WebSocket chat: ws://localhost:8000/ws/chat
- Command execution: POST /api/command
- REST endpoints: /chat, /agents, etc.
- API docs: http://localhost:8000/docs
"""

import sys
import os
from pathlib import Path

# Add langchain-agent-base to path
sys.path.insert(0, str(Path(__file__).parent / "langchain-agent-base" / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
from dotenv import load_dotenv

load_dotenv()

# Import your agent and commands
from cli import create_agent, AGENT_CONFIG, setup_agent_commands, _simple_memory
from commands import CommandRegistry

# Create FastAPI app
app = FastAPI(
    title=f"{AGENT_CONFIG.get('name', 'Agent')} API",
    description="CLI Agent exposed via REST API and WebSocket",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create agent instance
print(f"🤖 Initializing {AGENT_CONFIG.get('name')}...")
agent_instance = create_agent(project_root=".", enable_memory=True)

# Setup commands (same as CLI)
class MockCLI:
    """Mock CLI instance for command execution"""
    def __init__(self):
        self.colors = self._setup_colors()
        self.session_id = "api_session"
        self.enable_memory = True
        self.confirm_terminal = False
        self.confirm_tools = False
        self.agent = agent_instance
    
    def _setup_colors(self):
        """Return ANSI color codes for commands"""
        return {
            'primary': '\033[97m',      # White
            'accent': '\033[35m',       # Magenta
            'success': '\033[32m',      # Green
            'info': '\033[36m',         # Cyan
            'warning': '\033[33m',      # Yellow
            'error': '\033[31m',        # Red
            'secondary': '\033[90m',    # Gray
            'reset': '\033[0m'
        }
    
    def reinitialize_model(self):
        """Reinitialize agent"""
        pass

cli_instance = MockCLI()
commands_registry = setup_agent_commands(agent_instance, cli_instance)

print(f"✅ Agent ready with {len(commands_registry.commands)} commands")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": AGENT_CONFIG.get('name'),
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/chat",
            "command": "/api/command",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "agent": AGENT_CONFIG.get('name'),
        "cwd": os.getcwd()
    }


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with Next.js.
    
    Client sends:
    {
        "message": "hello world",
        "session_id": "xyz"
    }
    
    Server sends:
    {
        "type": "agent_response",
        "content": "...",
        "ansi": true
    }
    """
    await websocket.accept()
    print("🔌 WebSocket client connected")
    
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            session_id = data.get("session_id", "default")
            
            if not message:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message is required"
                })
                continue
            
            try:
                # Send typing indicator
                await websocket.send_json({
                    "type": "agent_typing",
                    "agent_name": AGENT_CONFIG.get('name')
                })
                
                # Check if it's a command (starts with //)
                if message.startswith("//"):
                    command_str = message[2:].strip()
                    
                    # Execute command using registry
                    try:
                        result = commands_registry.execute_command(command_str)
                        
                        await websocket.send_json({
                            "type": "command_result",
                            "command": command_str,
                            "result": result,
                            "ansi": True,
                            "cwd": os.getcwd()
                        })
                    except Exception as cmd_err:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Command error: {str(cmd_err)}",
                            "ansi": True
                        })
                else:
                    # Regular chat message
                    response = agent_instance.chat(
                        message,
                        session_id=session_id
                    )
                    
                    # Store in memory
                    if _simple_memory:
                        _simple_memory.add_message(session_id, message, response)
                    
                    await websocket.send_json({
                        "type": "agent_response",
                        "content": response,
                        "ansi": True,
                        "cwd": os.getcwd()
                    })
                    
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                print(f"❌ Error: {e}")
                
    except WebSocketDisconnect:
        print("🔌 WebSocket client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")


@app.post("/api/command")
async def execute_command(request: dict):
    """
    Execute CLI commands via REST API.
    
    Request:
    {
        "command": "cd",
        "args": ["path/to/dir"]
    }
    
    Response:
    {
        "result": "✓ Changed directory...",
        "success": true,
        "ansi": true,
        "cwd": "/new/path"
    }
    """
    try:
        command = request.get("command", "")
        args = request.get("args", [])
        
        if not command:
            return {
                "result": "Command is required",
                "success": False
            }
        
        # Build command string
        command_str = command
        if args:
            command_str += " " + " ".join(str(arg) for arg in args)
        
        # Execute via registry
        result = commands_registry.execute_command(command_str)
        
        return {
            "result": result,
            "success": True,
            "ansi": True,
            "cwd": os.getcwd()
        }
        
    except Exception as e:
        return {
            "result": f"\033[31mError: {str(e)}\033[0m",
            "success": False,
            "error": str(e),
            "ansi": True
        }


@app.get("/api/commands")
async def list_commands():
    """List all available commands"""
    commands = []
    for name, cmd_info in commands_registry.commands.items():
        commands.append({
            "name": name,
            "description": cmd_info.description,
            "usage": cmd_info.usage
        })
    
    return {
        "commands": commands,
        "total": len(commands)
    }


@app.get("/api/status")
async def get_status():
    """Get agent status"""
    return {
        "name": AGENT_CONFIG.get('name'),
        "provider": AGENT_CONFIG.get('provider'),
        "model": AGENT_CONFIG.get('model_name'),
        "cwd": os.getcwd(),
        "memory_enabled": cli_instance.enable_memory,
        "commands_available": len(commands_registry.commands)
    }


@app.post("/api/autocomplete")
async def autocomplete(request: dict):
    """
    Get autocomplete suggestions for commands and paths.
    
    Request:
    {
        "text": "//cd lang",
        "cursor_position": 8
    }
    
    Response:
    {
        "suggestions": ["langchain-agent-base/", "langchain-agent-base/src/"],
        "type": "path"  // or "command"
    }
    """
    try:
        text = request.get("text", "")
        cursor_pos = request.get("cursor_position", len(text))
        
        # Extract the part before cursor
        text_before_cursor = text[:cursor_pos]
        
        # Check if it's a command (starts with //)
        if text_before_cursor.startswith("//"):
            command_part = text_before_cursor[2:]
            
            # If there's a space, we're completing arguments (e.g., path for //cd)
            if " " in command_part:
                command_name = command_part.split()[0]
                arg_text = command_part.split(None, 1)[1] if len(command_part.split(None, 1)) > 1 else ""
                
                # For //cd, complete paths
                if command_name == "cd":
                    suggestions = get_path_completions(arg_text)
                    return {
                        "suggestions": suggestions,
                        "type": "path",
                        "prefix": arg_text
                    }
            else:
                # Complete command names
                all_commands = [f"//{name}" for name in commands_registry.commands.keys()]
                suggestions = [cmd for cmd in all_commands if cmd.startswith(text_before_cursor)]
                return {
                    "suggestions": suggestions,
                    "type": "command",
                    "prefix": text_before_cursor
                }
        else:
            # Regular text - suggest paths
            suggestions = get_path_completions(text_before_cursor)
            return {
                "suggestions": suggestions,
                "type": "path",
                "prefix": text_before_cursor
            }
        
        return {"suggestions": [], "type": "none"}
        
    except Exception as e:
        return {
            "suggestions": [],
            "error": str(e)
        }


def get_path_completions(partial_path: str, max_results: int = 10):
    """Get path completions for autocomplete"""
    try:
        from pathlib import Path
        import os
        
        # Expand user home
        partial_path = os.path.expanduser(partial_path)
        
        # If empty, suggest current directory contents
        if not partial_path:
            base_dir = Path.cwd()
            pattern = "*"
        else:
            # Split into directory and filename parts
            path = Path(partial_path)
            
            if partial_path.endswith(('/', '\\')):
                # User typed trailing slash, show contents of that dir
                base_dir = path
                pattern = "*"
            else:
                # Show completions in parent directory
                base_dir = path.parent if path.parent != path else Path.cwd()
                pattern = path.name + "*"
        
        # Get matching paths
        if not base_dir.exists():
            return []
        
        matches = []
        for item in base_dir.glob(pattern):
            relative_path = str(item.relative_to(Path.cwd())) if item.is_relative_to(Path.cwd()) else str(item)
            
            # Add trailing slash for directories
            if item.is_dir():
                relative_path += os.sep
            
            matches.append(relative_path)
            
            if len(matches) >= max_results:
                break
        
        return sorted(matches)
        
    except Exception as e:
        print(f"Path completion error: {e}")
        return []


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🚀 Starting {AGENT_CONFIG.get('name')} API Server")
    print(f"{'='*60}")
    print(f"\n📡 Endpoints:")
    print(f"   • WebSocket Chat:    ws://localhost:8000/ws/chat")
    print(f"   • Command Execute:   POST http://localhost:8000/api/command")
    print(f"   • Status:            GET http://localhost:8000/api/status")
    print(f"   • API Docs:          http://localhost:8000/docs")
    print(f"\n💡 For Next.js, connect to: ws://localhost:8000/ws/chat")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
