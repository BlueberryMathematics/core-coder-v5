"""
Agent Card Storage with Qdrant Integration
==========================================

Provides persistent storage for AgentCards in Qdrant vector database
with semantic search capabilities and metadata management.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    from langchain_huggingface import HuggingFaceEmbeddings
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

from .protocol import AgentCard, AgentStatus


class UnifiedQdrantStorage:
    """
    Unified Qdrant storage for both AgentCards and RAG documents.
    Enables optional RAG search across agent cards and conversation history.
    """
    
    def __init__(self,
                 qdrant_url: str = "localhost:6333",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 vector_size: int = 384):
        """Initialize unified Qdrant storage."""
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant dependencies not available. Install with: pip install qdrant-client sentence-transformers")
        
        self.client = QdrantClient(url=qdrant_url)
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.vector_size = vector_size
        
        # Collection names for different data types
        self.collections = {
            "agent_cards": "agent_cards",
            "conversations": "conversation_history", 
            "documents": "rag_documents"
        }
        
        self._setup_collections()
    
    def _setup_collections(self):
        """Setup all required collections."""
        for collection_name in self.collections.values():
            if not self.client.collection_exists(collection_name):
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
    
    def get_agent_storage(self) -> 'AgentCardStorage':
        """Get AgentCardStorage using this unified client."""
        return AgentCardStorage(
            qdrant_client=self.client,
            collection_name=self.collections["agent_cards"],
            embeddings=self.embeddings
        )
    
    def get_conversation_storage(self) -> 'ConversationMemoryStorage':
        """Get ConversationMemoryStorage using this unified client.""" 
        return ConversationMemoryStorage(
            qdrant_client=self.client,
            collection_name=self.collections["conversations"],
            embeddings=self.embeddings
        )
    
    def get_rag_storage(self, collection_name: str = "documents") -> 'RAGDocumentStorage':
        """Get RAG document storage using this unified client."""
        return RAGDocumentStorage(
            qdrant_client=self.client,
            collection_name=collection_name,
            embeddings=self.embeddings
        )


class AgentCardStorage:
    """
    Qdrant-based storage for AgentCards with semantic search capabilities.
    """
    
    def __init__(self, 
                 qdrant_url: str = "localhost:6333",
                 collection_name: str = "agent_cards",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 vector_size: int = 384,
                 qdrant_client: QdrantClient = None,
                 embeddings = None):
        """
        Initialize Qdrant storage for agent cards.
        
        Args:
            qdrant_url: Qdrant server URL (ignored if qdrant_client provided)
            collection_name: Collection name for agent cards
            embedding_model: HuggingFace embedding model (ignored if embeddings provided)
            vector_size: Vector dimension size
            qdrant_client: Existing Qdrant client (for unified storage)
            embeddings: Existing embeddings instance (for unified storage)
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant dependencies not available. Install with: pip install qdrant-client sentence-transformers")
        
        self.collection_name = collection_name
        self.client = qdrant_client or QdrantClient(url=qdrant_url)
        self.embeddings = embeddings or HuggingFaceEmbeddings(model_name=embedding_model)
        self.vector_size = vector_size
        
        # Initialize collection
        self._setup_collection()
    
    def _setup_collection(self):
        """Setup Qdrant collection for agent cards."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"✅ Created Qdrant collection: {self.collection_name}")
            else:
                print(f"📂 Using existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            print(f"⚠️ Error setting up Qdrant collection: {e}")
    
    def _create_embedding_text(self, card: AgentCard) -> str:
        """Create text for embedding generation."""
        embedding_text = f"""
        Name: {card.name}
        Domain: {card.domain}
        Category: {card.category}
        Description: {card.description}
        System Prompt: {card.system_prompt}
        Tools: {', '.join(card.tools)}
        Commands: {', '.join(card.commands)}
        Author: {card.author}
        """.strip()
        
        return embedding_text
    
    async def store_agent_card(self, card: AgentCard) -> str:
        """
        Store agent card in Qdrant with semantic embedding.
        
        Args:
            card: AgentCard to store
            
        Returns:
            Point ID in Qdrant
        """
        try:
            # Generate embedding
            embedding_text = self._create_embedding_text(card)
            embedding = self.embeddings.embed_query(embedding_text)
            
            # Create point ID
            point_id = f"{card.name}_{card.version}_{card.config_hash}"
            
            # Prepare payload
            payload = card.to_dict()
            payload.update({
                "embedding_text": embedding_text,
                "searchable_text": f"{card.name} {card.domain} {card.category} {card.description}".lower()
            })
            
            # Store in Qdrant
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            print(f"✅ Stored agent card: {card.name} v{card.version}")
            return point_id
            
        except Exception as e:
            print(f"❌ Error storing agent card: {e}")
            raise
    
    async def retrieve_agent_card(self, name: str, version: str = None) -> Optional[AgentCard]:
        """
        Retrieve agent card from Qdrant.
        
        Args:
            name: Agent name
            version: Agent version (if None, gets latest)
            
        Returns:
            AgentCard if found
        """
        try:
            # Build filter
            filters = [
                FieldCondition(key="name", match=MatchValue(value=name))
            ]
            
            if version:
                filters.append(
                    FieldCondition(key="version", match=MatchValue(value=version))
                )
            
            # Search
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=filters),
                limit=10 if not version else 1
            )
            
            if not results[0]:  # No points found
                return None
            
            if version:
                # Return specific version
                point = results[0][0]
                return AgentCard.from_dict(point.payload)
            else:
                # Return latest version
                points = results[0]
                latest_point = max(points, key=lambda p: p.payload['updated_at'])
                return AgentCard.from_dict(latest_point.payload)
                
        except Exception as e:
            print(f"❌ Error retrieving agent card: {e}")
            return None
    
    async def search_agents(self, 
                          query: str, 
                          domain: str = None,
                          category: str = None,
                          status: AgentStatus = None,
                          limit: int = 10) -> List[AgentCard]:
        """
        Semantic search for agents based on query.
        
        Args:
            query: Search query
            domain: Filter by domain
            category: Filter by category  
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of matching AgentCards
        """
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Build filters
            filters = []
            if domain:
                filters.append(FieldCondition(key="domain", match=MatchValue(value=domain)))
            if category:
                filters.append(FieldCondition(key="category", match=MatchValue(value=category)))
            if status:
                filters.append(FieldCondition(key="status", match=MatchValue(value=status.value)))
            
            search_filter = Filter(must=filters) if filters else None
            
            # Semantic search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                with_payload=True
            )
            
            # Convert to AgentCards
            agent_cards = []
            for result in results:
                card = AgentCard.from_dict(result.payload)
                agent_cards.append(card)
            
            return agent_cards
            
        except Exception as e:
            print(f"❌ Error searching agents: {e}")
            return []
    
    async def list_all_agents(self, 
                            domain: str = None,
                            status: AgentStatus = None) -> List[AgentCard]:
        """
        List all stored agent cards with optional filtering.
        
        Args:
            domain: Filter by domain
            status: Filter by status
            
        Returns:
            List of AgentCards
        """
        try:
            filters = []
            if domain:
                filters.append(FieldCondition(key="domain", match=MatchValue(value=domain)))
            if status:
                filters.append(FieldCondition(key="status", match=MatchValue(value=status.value)))
            
            search_filter = Filter(must=filters) if filters else None
            
            # Scroll through all points
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=search_filter,
                limit=1000  # Adjust based on expected number of agents
            )
            
            agent_cards = []
            for point in results[0]:
                card = AgentCard.from_dict(point.payload)
                agent_cards.append(card)
            
            return sorted(agent_cards, key=lambda x: (x.name, x.version))
            
        except Exception as e:
            print(f"❌ Error listing agents: {e}")
            return []
    
    async def update_agent_status(self, name: str, version: str, status: AgentStatus):
        """Update agent status in storage."""
        try:
            card = await self.retrieve_agent_card(name, version)
            if card:
                card.status = status
                card.updated_at = datetime.now().isoformat()
                await self.store_agent_card(card)
                print(f"✅ Updated {name}:{version} status to {status.value}")
            else:
                print(f"⚠️ Agent {name}:{version} not found for status update")
                
        except Exception as e:
            print(f"❌ Error updating agent status: {e}")
    
    async def delete_agent_card(self, name: str, version: str) -> bool:
        """
        Delete agent card from storage.
        
        Args:
            name: Agent name
            version: Agent version
            
        Returns:
            True if deleted successfully
        """
        try:
            # Find the point
            filters = [
                FieldCondition(key="name", match=MatchValue(value=name)),
                FieldCondition(key="version", match=MatchValue(value=version))
            ]
            
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=filters),
                limit=1
            )
            
            if results[0]:
                point_id = results[0][0].id
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=[point_id]
                )
                print(f"✅ Deleted agent card: {name} v{version}")
                return True
            else:
                print(f"⚠️ Agent card not found: {name} v{version}")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting agent card: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "total_agents": collection_info.points_count,
                "collection_name": self.collection_name,
                "vector_size": self.vector_size,
                "status": "healthy"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }


# Integration with AgentRegistry
class ConversationMemoryStorage:
    """
    Qdrant-based storage for conversation history with temporal and semantic search.
    """
    
    def __init__(self,
                 qdrant_client: QdrantClient,
                 collection_name: str = "conversation_history",
                 embeddings = None):
        """Initialize conversation memory storage."""
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embeddings = embeddings
        
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # Default embedding size
                    distance=Distance.COSINE
                )
            )
    
    async def store_message(self, 
                          session_id: str,
                          message: str,
                          response: str,
                          timestamp: datetime,
                          urls: List[str] = None,
                          metadata: Dict[str, Any] = None) -> str:
        """Store conversation message with metadata."""
        # Create searchable text combining message and response
        searchable_text = f"User: {message}\nAssistant: {response}"
        
        # Generate embedding
        embedding = self.embeddings.embed_query(searchable_text)
        
        # Create point with UUID
        import uuid
        point_id = str(uuid.uuid4())
        payload = {
            "session_id": session_id,
            "message": message,
            "response": response,
            "timestamp": timestamp.isoformat(),
            "urls": urls or [],
            "metadata": metadata or {},
            "searchable_text": searchable_text
        }
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return point_id
    
    async def search_conversations(self,
                                 query: str,
                                 session_id: str = None,
                                 start_time: datetime = None,
                                 end_time: datetime = None,
                                 urls: List[str] = None,
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversation history with filters."""
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)
        
        # Build filters
        filters = []
        if session_id:
            filters.append(FieldCondition(key="session_id", match=MatchValue(value=session_id)))
        if start_time:
            filters.append(FieldCondition(key="timestamp", range={"gte": start_time.isoformat()}))
        if end_time:
            filters.append(FieldCondition(key="timestamp", range={"lte": end_time.isoformat()}))
        if urls:
            for url in urls:
                filters.append(FieldCondition(key="urls", match=MatchValue(value=url)))
        
        search_filter = Filter(must=filters) if filters else None
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "message": result.payload["message"],
                "response": result.payload["response"],
                "timestamp": result.payload["timestamp"],
                "urls": result.payload["urls"],
                "metadata": result.payload["metadata"]
            }
            for result in results
        ]

    async def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for a session."""
        try:
            filters = [
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ]
            
            # Scroll to get messages
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=filters),
                limit=100,  # Fetch more to ensure we get the latest
                with_payload=True
            )
            
            messages = []
            for result in results:
                messages.append({
                    "timestamp": datetime.fromisoformat(result.payload["timestamp"]),
                    "message": result.payload["message"],
                    "response": result.payload["response"],
                    "urls": result.payload.get("urls", [])
                })
            
            # Sort by timestamp
            messages.sort(key=lambda x: x["timestamp"])
            
            return messages[-limit:]
            
        except Exception as e:
            print(f"⚠️ Error retrieving recent messages: {e}")
            return []


class RAGDocumentStorage:
    """
    Qdrant-based storage for RAG documents with unified search.
    """
    
    def __init__(self,
                 qdrant_client: QdrantClient,
                 collection_name: str,
                 embeddings = None):
        """Initialize RAG document storage."""
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embeddings = embeddings
        
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # Default embedding size
                    distance=Distance.COSINE
                )
            )
    
    async def store_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Store documents with metadata."""
        points = []
        
        for i, doc in enumerate(documents):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            # Generate embedding
            embedding = self.embeddings.embed_query(content)
            
            point_id = f"{self.collection_name}_{i}_{datetime.now().timestamp()}"
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "content": content,
                    "metadata": metadata,
                    "timestamp": datetime.now().isoformat()
                }
            )
            points.append(point)
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return [p.id for p in points]
    
    async def search_documents(self,
                             query: str,
                             filters: Dict[str, Any] = None,
                             limit: int = 10) -> List[Dict[str, Any]]:
        """Search documents with optional filters."""
        query_embedding = self.embeddings.embed_query(query)
        
        # Build filters if provided
        search_filter = None
        if filters:
            filter_conditions = []
            for key, value in filters.items():
                filter_conditions.append(FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value)))
            search_filter = Filter(must=filter_conditions)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": result.id,
                "score": result.score,
                "content": result.payload["content"],
                "metadata": result.payload["metadata"],
                "timestamp": result.payload["timestamp"]
            }
            for result in results
        ]


class QdrantAgentRegistry:
    """
    Enhanced AgentRegistry that uses Qdrant for persistent storage.
    """
    
    def __init__(self, 
                 storage_path: str = "agent_registry.json",
                 qdrant_url: str = "localhost:6333",
                 use_qdrant: bool = True):
        """
        Initialize registry with optional Qdrant storage.
        
        Args:
            storage_path: JSON file for local backup
            qdrant_url: Qdrant server URL
            use_qdrant: Whether to use Qdrant storage
        """
        from .protocol import AgentRegistry
        
        self.local_registry = AgentRegistry(storage_path)
        self.use_qdrant = use_qdrant and QDRANT_AVAILABLE
        
        if self.use_qdrant:
            try:
                self.qdrant_storage = AgentCardStorage(qdrant_url=qdrant_url)
                print("✅ Qdrant storage enabled for agent registry")
            except Exception as e:
                print(f"⚠️ Failed to initialize Qdrant storage: {e}")
                self.use_qdrant = False
    
    async def register_agent(self, *args, **kwargs) -> AgentCard:
        """Register agent with both local and Qdrant storage."""
        # Register with local registry
        card = self.local_registry.register_agent(*args, **kwargs)
        
        # Store in Qdrant if available
        if self.use_qdrant:
            try:
                await self.qdrant_storage.store_agent_card(card)
            except Exception as e:
                print(f"⚠️ Failed to store in Qdrant: {e}")
        
        return card
    
    async def search_agents(self, query: str, **kwargs) -> List[AgentCard]:
        """Semantic search using Qdrant if available."""
        if self.use_qdrant:
            return await self.qdrant_storage.search_agents(query, **kwargs)
        else:
            # Fallback to local search
            return self.local_registry.list_agents(**kwargs)
    
    def get_agent_card(self, name: str, version: str = None) -> Optional[AgentCard]:
        """Get agent card (sync method for compatibility)."""
        return self.local_registry.get_agent_card(name, version)
    
    def create_agent_instance(self, *args, **kwargs):
        """Create agent instance."""
        return self.local_registry.create_agent_instance(*args, **kwargs)
    
    def list_agents(self, **kwargs) -> List[AgentCard]:
        """List agents from local registry."""
        return self.local_registry.list_agents(**kwargs)


# Factory function for easy setup
def create_agent_storage(use_qdrant: bool = True, **kwargs) -> QdrantAgentRegistry:
    """
    Create agent storage with optional Qdrant integration.
    
    Args:
        use_qdrant: Whether to use Qdrant storage
        **kwargs: Additional arguments for QdrantAgentRegistry
        
    Returns:
        Configured agent registry
    """
    return QdrantAgentRegistry(use_qdrant=use_qdrant, **kwargs)
