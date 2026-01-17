"""
LangChain Agent Base Protocol
============================

A comprehensive protocol system for building, versioning, and deploying agents
with automatic API generation, metadata management, and extensibility.

This protocol allows users to:
1. Extend base Agent classes for specialized domains (math, science, etc.)
2. Automatic versioning and metadata management through AgentCards
3. Auto-generated FastAPI endpoints for all agent methods
4. Dynamic tool and command discovery
5. Qdrant storage for agent configurations and metadata

Usage:
    from .protocol import AgentProtocol, AgentCard, register_agent
    from .base import Agent
    
    # Create specialized agent
    @register_agent("math", version="1.0.0")
    class MathAgent(Agent):
        def __init__(self):
            super().__init__(
                system_prompt="Advanced mathematical assistant",
                tools=get_math_tools()
            )
    
    # Automatically generates API endpoints and stores metadata
    protocol = AgentProtocol()
    protocol.run_server()  # FastAPI server with all registered agents
"""

import json
import inspect
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from abc import ABC, abstractmethod
import semver
from enum import Enum

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse


class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ToolType(str, Enum):
    """Types of tools available."""
    MATH = "math"
    SCIENCE = "science"
    CODING = "coding"
    RAG = "rag"
    API = "api"
    CUSTOM = "custom"


@dataclass
class AgentCard:
    """
    Agent metadata card for storing agent configurations and versions.
    Designed for JSON serialization and Qdrant storage.
    """
    
    # Identity
    name: str
    version: str
    description: str
    
    # Classification
    domain: str  # math, science, coding, general
    category: str  # specialist, general-purpose, multi-domain
    
    # Configuration
    system_prompt: str
    model_name: str = "openai/gpt-oss-120b"
    temperature: float = 0.0
    
    # Capabilities
    tools: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    
    # Metadata
    author: str = "Unknown"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: AgentStatus = AgentStatus.DEVELOPMENT
    
    # Technical
    class_path: str = ""  # Full import path to the agent class
    dependencies: List[str] = field(default_factory=list)
    config_hash: str = field(default="", init=False)
    
    # Performance
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    usage_stats: Dict[str, Any] = field(default_factory=dict)
    
    # Relationships
    extends: Optional[str] = None  # Base agent this extends
    compatible_with: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate configuration hash after initialization."""
        self.config_hash = self._calculate_hash()
        
    def _calculate_hash(self) -> str:
        """Calculate hash of critical configuration parameters."""
        config_data = {
            "system_prompt": self.system_prompt,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "tools": sorted(self.tools),
            "commands": sorted(self.commands)
        }
        config_str = json.dumps(config_data, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCard':
        """Create AgentCard from dictionary."""
        # Remove config_hash if present (it's calculated in __post_init__)
        data_copy = data.copy()
        data_copy.pop('config_hash', None)
        return cls(**data_copy)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentCard':
        """Create AgentCard from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def update_version(self, increment_type: str = "patch") -> str:
        """
        Update version using semantic versioning.
        
        Args:
            increment_type: "major", "minor", or "patch"
        
        Returns:
            New version string
        """
        try:
            new_version = semver.bump_version(self.version, increment_type)
            self.version = new_version
            self.updated_at = datetime.now().isoformat()
            self.config_hash = self._calculate_hash()
            return new_version
        except Exception:
            # Fallback for non-semver versions
            parts = self.version.split('.')
            if len(parts) != 3:
                self.version = "1.0.0"
                return self.version
                
            major, minor, patch = map(int, parts)
            if increment_type == "major":
                major += 1
                minor = patch = 0
            elif increment_type == "minor":
                minor += 1
                patch = 0
            else:  # patch
                patch += 1
                
            self.version = f"{major}.{minor}.{patch}"
            self.updated_at = datetime.now().isoformat()
            self.config_hash = self._calculate_hash()
            return self.version
    
    def is_compatible_with(self, other_version: str) -> bool:
        """Check if this version is compatible with another version."""
        try:
            return semver.match(other_version, f"^{self.version}")
        except Exception:
            return self.version == other_version


class AgentRegistry:
    """
    Central registry for managing agent classes, versions, and metadata.
    Provides automatic discovery, versioning, and API generation.
    """
    
    def __init__(self, storage_path: str = "agent_registry.json"):
        self.storage_path = Path(storage_path)
        self.agents: Dict[str, Dict[str, AgentCard]] = {}  # {agent_name: {version: card}}
        self.classes: Dict[str, Type] = {}  # {agent_name: class}
        self.load_registry()
    
    def register_agent(self, 
                      agent_class: Type,
                      name: str,
                      version: str = "1.0.0",
                      domain: str = "general",
                      category: str = "specialist",
                      description: str = None,
                      author: str = "Unknown",
                      status: AgentStatus = AgentStatus.DEVELOPMENT) -> AgentCard:
        """
        Register an agent class with the protocol.
        
        Args:
            agent_class: The agent class to register
            name: Agent name
            version: Version string (semver format)
            domain: Domain (math, science, coding, general)
            category: Category (specialist, general-purpose, multi-domain)
            description: Agent description
            author: Author name
            status: Development status
        
        Returns:
            Created AgentCard
        """
        # Extract metadata from class
        class_info = self._extract_class_metadata(agent_class)
        
        # Create agent card
        card = AgentCard(
            name=name,
            version=version,
            description=description or class_info.get("description", f"{name} agent"),
            domain=domain,
            category=category,
            system_prompt=class_info.get("system_prompt", ""),
            model_name=class_info.get("model_name", "openai/gpt-oss-120b"),
            temperature=class_info.get("temperature", 0.0),
            tools=class_info.get("tools", []),
            commands=class_info.get("commands", []),
            author=author,
            status=status,
            class_path=f"{agent_class.__module__}.{agent_class.__name__}",
            extends=class_info.get("extends"),
            dependencies=class_info.get("dependencies", [])
        )
        
        # Store in registry
        if name not in self.agents:
            self.agents[name] = {}
        
        self.agents[name][version] = card
        self.classes[f"{name}:{version}"] = agent_class
        
        # Save to disk
        self.save_registry()
        
        print(f"✅ Registered {name} v{version} ({domain} agent)")
        return card
    
    def _extract_class_metadata(self, agent_class: Type) -> Dict[str, Any]:
        """Extract metadata from agent class."""
        metadata = {}
        
        # Try to get default parameters from __init__
        try:
            init_signature = inspect.signature(agent_class.__init__)
            for param_name, param in init_signature.parameters.items():
                if param_name == 'self':
                    continue
                if param.default != inspect.Parameter.empty:
                    if param_name == 'system_prompt':
                        metadata['system_prompt'] = param.default
                    elif param_name == 'model_name':
                        metadata['model_name'] = param.default
                    elif param_name == 'temperature':
                        metadata['temperature'] = param.default
        except Exception:
            pass
        
        # Check for class attributes
        for attr_name in ['system_prompt', 'model_name', 'temperature', 'tools', 'commands']:
            if hasattr(agent_class, attr_name):
                metadata[attr_name] = getattr(agent_class, attr_name)
        
        # Get description from docstring
        if agent_class.__doc__:
            metadata['description'] = agent_class.__doc__.strip().split('\n')[0]
        
        # Check inheritance
        for base in agent_class.__bases__:
            if base.__name__ != 'Agent' and hasattr(base, '__name__'):
                metadata['extends'] = base.__name__
                break
        
        return metadata
    
    def get_agent_card(self, name: str, version: str = None) -> Optional[AgentCard]:
        """Get agent card by name and version."""
        if name not in self.agents:
            return None
        
        if version is None:
            # Get latest version
            versions = list(self.agents[name].keys())
            if not versions:
                return None
            # Sort versions and get latest
            try:
                latest_version = max(versions, key=lambda v: semver.VersionInfo.parse(v))
            except Exception:
                latest_version = sorted(versions)[-1]
            return self.agents[name][latest_version]
        
        return self.agents[name].get(version)
    
    def create_agent_instance(self, name: str, version: str = None, **kwargs):
        """Create instance of registered agent."""
        card = self.get_agent_card(name, version)
        if not card:
            raise ValueError(f"Agent {name}:{version} not found")
        
        class_key = f"{name}:{card.version}"
        if class_key not in self.classes:
            raise ValueError(f"Agent class {class_key} not loaded")
        
        agent_class = self.classes[class_key]
        return agent_class(**kwargs)
    
    def list_agents(self, domain: str = None, status: AgentStatus = None) -> List[AgentCard]:
        """List all registered agents with optional filtering."""
        agents = []
        
        for agent_name, versions in self.agents.items():
            for version, card in versions.items():
                if domain and card.domain != domain:
                    continue
                if status and card.status != status:
                    continue
                agents.append(card)
        
        return sorted(agents, key=lambda x: (x.name, x.version))
    
    def update_agent_status(self, name: str, version: str, status: AgentStatus):
        """Update agent status."""
        card = self.get_agent_card(name, version)
        if card:
            card.status = status
            card.updated_at = datetime.now().isoformat()
            self.save_registry()
    
    def save_registry(self):
        """Save registry to disk."""
        data = {}
        for agent_name, versions in self.agents.items():
            data[agent_name] = {}
            for version, card in versions.items():
                data[agent_name][version] = card.to_dict()
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_registry(self):
        """Load registry from disk."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            for agent_name, versions in data.items():
                self.agents[agent_name] = {}
                for version, card_data in versions.items():
                    self.agents[agent_name][version] = AgentCard.from_dict(card_data)
                    
        except Exception as e:
            print(f"Error loading registry: {e}")


# Global registry instance
_global_registry = None


def get_agent_registry() -> AgentRegistry:
    """Get global agent registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def register_agent(name: str, 
                  version: str = "1.0.0",
                  domain: str = "general",
                  category: str = "specialist",
                  description: str = None,
                  author: str = "Unknown",
                  status: AgentStatus = AgentStatus.DEVELOPMENT):
    """
    Decorator to register agent classes with the protocol.
    
    Usage:
        @register_agent("math", version="1.0.0", domain="math")
        class MathAgent(Agent):
            pass
    """
    def decorator(agent_class: Type):
        registry = get_agent_registry()
        registry.register_agent(
            agent_class=agent_class,
            name=name,
            version=version,
            domain=domain,
            category=category,
            description=description,
            author=author,
            status=status
        )
        return agent_class
    
    return decorator


# Pydantic models for API
class ChatRequest(BaseModel):
    message: str
    agent_name: str
    agent_version: Optional[str] = None
    session_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is 2 + 2?",
                "agent_name": "math",
                "agent_version": "1.0.0",
                "session_id": "user123_session1"
            }
        }


class ChatResponse(BaseModel):
    response: str
    agent_name: str
    agent_version: str
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class CommandRequest(BaseModel):
    command: str
    agent_name: str
    agent_version: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "command": "calc",
                "agent_name": "math", 
                "agent_version": "1.0.0",
                "parameters": {"expression": "2 + 2"}
            }
        }


class CommandResponse(BaseModel):
    result: str
    command: str
    agent_name: str
    agent_version: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentListResponse(BaseModel):
    agents: List[Dict[str, Any]]
    total: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
