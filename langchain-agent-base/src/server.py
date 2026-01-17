"""
Agent Protocol FastAPI Server
=============================

Automatically generates FastAPI endpoints for all registered agents,
tools, and commands. Provides a complete REST API for agent interactions.
"""

from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn
import asyncio
from datetime import datetime
import json

from .protocol import (
    AgentRegistry, get_agent_registry, AgentCard, AgentStatus,
    ChatRequest, ChatResponse, CommandRequest, CommandResponse, AgentListResponse
)


class AgentProtocolServer:
    """
    FastAPI server that automatically generates endpoints for registered agents.
    """
    
    def __init__(self, registry: AgentRegistry = None):
        self.registry = registry or get_agent_registry()
        self.app = FastAPI(
            title="LangChain Agent Base Protocol API",
            description="Automatically generated API for registered agents",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Session management (simple in-memory for now)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        # Agent management endpoints
        @self.app.get("/agents", response_model=AgentListResponse)
        async def list_agents(domain: Optional[str] = None, status: Optional[str] = None):
            """List all registered agents."""
            try:
                status_enum = AgentStatus(status) if status else None
            except ValueError:
                status_enum = None
                
            agents = self.registry.list_agents(domain=domain, status=status_enum)
            return AgentListResponse(
                agents=[agent.to_dict() for agent in agents],
                total=len(agents),
                filters_applied={"domain": domain, "status": status}
            )
        
        @self.app.get("/agents/{agent_name}")
        async def get_agent_info(agent_name: str, version: Optional[str] = None):
            """Get detailed information about a specific agent."""
            card = self.registry.get_agent_card(agent_name, version)
            if not card:
                raise HTTPException(status_code=404, detail=f"Agent {agent_name}:{version} not found")
            return card.to_dict()
        
        @self.app.get("/agents/{agent_name}/versions")
        async def get_agent_versions(agent_name: str):
            """Get all versions of a specific agent."""
            if agent_name not in self.registry.agents:
                raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
            
            versions = []
            for version, card in self.registry.agents[agent_name].items():
                versions.append({
                    "version": version,
                    "status": card.status,
                    "created_at": card.created_at,
                    "updated_at": card.updated_at,
                    "description": card.description
                })
            
            return {"agent_name": agent_name, "versions": versions}
        
        # Chat endpoints
        @self.app.post("/chat", response_model=ChatResponse)
        async def chat_with_agent(request: ChatRequest):
            """Send a message to an agent and get a response."""
            try:
                # Get agent instance
                agent = self.registry.create_agent_instance(
                    request.agent_name, 
                    request.agent_version
                )
                
                # Get agent card for version info
                card = self.registry.get_agent_card(request.agent_name, request.agent_version)
                
                # Process message
                response = agent.chat(request.message)
                
                # Update session if provided
                if request.session_id:
                    self._update_session(request.session_id, request.message, response, card)
                
                return ChatResponse(
                    response=response,
                    agent_name=request.agent_name,
                    agent_version=card.version,
                    session_id=request.session_id
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/chat/stream")
        async def stream_chat_with_agent(request: ChatRequest):
            """Stream chat response from agent."""
            try:
                agent = self.registry.create_agent_instance(
                    request.agent_name, 
                    request.agent_version
                )
                
                async def generate_stream():
                    try:
                        for chunk in agent.stream_chat(request.message):
                            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\\n\\n"
                        yield f"data: {json.dumps({'chunk': '', 'done': True})}\\n\\n"
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\\n\\n"
                
                return StreamingResponse(
                    generate_stream(), 
                    media_type="text/plain",
                    headers={"Cache-Control": "no-cache"}
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Command endpoints  
        @self.app.post("/command", response_model=CommandResponse)
        async def execute_command(request: CommandRequest):
            """Execute a command on an agent."""
            try:
                agent = self.registry.create_agent_instance(
                    request.agent_name,
                    request.agent_version,
                    enable_commands=True  # Ensure commands are enabled
                )
                
                card = self.registry.get_agent_card(request.agent_name, request.agent_version)
                
                # Execute command
                result = agent.execute_command(request.command, **request.parameters)
                
                return CommandResponse(
                    result=result,
                    command=request.command,
                    agent_name=request.agent_name,
                    agent_version=card.version
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/agents/{agent_name}/commands")
        async def list_agent_commands(agent_name: str, version: Optional[str] = None):
            """List all commands available for an agent."""
            try:
                agent = self.registry.create_agent_instance(
                    agent_name, 
                    version,
                    enable_commands=True
                )
                
                commands = agent.list_commands()
                
                # Get command details
                command_details = []
                for cmd in commands:
                    try:
                        help_info = agent.execute_command("help", command_name=cmd)
                        command_details.append({
                            "name": cmd,
                            "help": help_info
                        })
                    except Exception:
                        command_details.append({
                            "name": cmd,
                            "help": f"Execute {cmd} command"
                        })
                
                return {
                    "agent_name": agent_name,
                    "version": version,
                    "commands": command_details
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Tool endpoints
        @self.app.get("/agents/{agent_name}/tools")
        async def list_agent_tools(agent_name: str, version: Optional[str] = None):
            """List all tools available for an agent."""
            try:
                agent = self.registry.create_agent_instance(agent_name, version)
                tools = agent.list_tools()
                
                return {
                    "agent_name": agent_name,
                    "version": version,
                    "tools": tools
                }
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Session management
        @self.app.get("/sessions/{session_id}")
        async def get_session(session_id: str):
            """Get session history."""
            if session_id not in self.sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            
            return self.sessions[session_id]
        
        @self.app.delete("/sessions/{session_id}")
        async def clear_session(session_id: str):
            """Clear session history."""
            if session_id in self.sessions:
                del self.sessions[session_id]
                return {"message": f"Session {session_id} cleared"}
            else:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # Registry management endpoints
        @self.app.post("/agents/{agent_name}/versions/{version}/status")
        async def update_agent_status(agent_name: str, version: str, status: str):
            """Update agent status."""
            try:
                status_enum = AgentStatus(status)
                self.registry.update_agent_status(agent_name, version, status_enum)
                return {"message": f"Updated {agent_name}:{version} status to {status}"}
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Discovery endpoints
        @self.app.get("/discovery/domains")
        async def get_available_domains():
            """Get all available agent domains."""
            agents = self.registry.list_agents()
            domains = list(set(agent.domain for agent in agents))
            return {"domains": sorted(domains)}
        
        @self.app.get("/discovery/categories") 
        async def get_available_categories():
            """Get all available agent categories."""
            agents = self.registry.list_agents()
            categories = list(set(agent.category for agent in agents))
            return {"categories": sorted(categories)}
        
        # Batch operations
        @self.app.post("/batch/chat")
        async def batch_chat(requests: List[ChatRequest]):
            """Process multiple chat requests in parallel."""
            async def process_request(req):
                try:
                    agent = self.registry.create_agent_instance(req.agent_name, req.agent_version)
                    response = agent.chat(req.message)
                    card = self.registry.get_agent_card(req.agent_name, req.agent_version)
                    
                    return ChatResponse(
                        response=response,
                        agent_name=req.agent_name,
                        agent_version=card.version,
                        session_id=req.session_id
                    )
                except Exception as e:
                    return {"error": str(e), "agent_name": req.agent_name}
            
            # Process requests in parallel
            tasks = [process_request(req) for req in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {"results": results}
    
    def _update_session(self, session_id: str, message: str, response: str, card: AgentCard):
        """Update session with new message exchange."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "exchanges": []
            }
        
        self.sessions[session_id]["exchanges"].append({
            "timestamp": datetime.now().isoformat(),
            "user_message": message,
            "agent_response": response,
            "agent_name": card.name,
            "agent_version": card.version
        })
        
        # Keep only last 100 exchanges per session
        if len(self.sessions[session_id]["exchanges"]) > 100:
            self.sessions[session_id]["exchanges"] = self.sessions[session_id]["exchanges"][-100:]
    
    def run(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
        """Run the FastAPI server."""
        print(f"🚀 Starting Agent Protocol Server on {host}:{port}")
        print(f"📚 API Documentation: http://{host}:{port}/docs")
        print(f"🔍 Redoc Documentation: http://{host}:{port}/redoc")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload
        )


class AgentProtocol:
    """
    Main protocol class that combines registry and server.
    """
    
    def __init__(self, registry_path: str = "agent_registry.json"):
        self.registry = AgentRegistry(registry_path)
        self.server = AgentProtocolServer(self.registry)
    
    def register_agent(self, *args, **kwargs):
        """Register an agent with the protocol."""
        return self.registry.register_agent(*args, **kwargs)
    
    def run_server(self, **kwargs):
        """Run the FastAPI server."""
        self.server.run(**kwargs)
    
    def get_app(self):
        """Get the FastAPI app for custom deployment."""
        return self.server.app


# Global protocol instance
_global_protocol = None


def get_protocol() -> AgentProtocol:
    """Get global protocol instance."""
    global _global_protocol
    if _global_protocol is None:
        _global_protocol = AgentProtocol()
    return _global_protocol


def run_protocol_server(**kwargs):
    """Run the protocol server with registered agents."""
    protocol = get_protocol()
    protocol.run_server(**kwargs)


if __name__ == "__main__":
    # Run server if called directly
    run_protocol_server()
