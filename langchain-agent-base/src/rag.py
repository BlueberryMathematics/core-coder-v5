"""
RAG (Retrieval-Augmented Generation) Manager
============================================

Class-based RAG system for document indexing and retrieval.
Supports web scraping, document loading, and vector search.
"""

import os
import bs4
from typing import List, Optional, Dict, Any
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import create_retriever_tool
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


class RAGManager:
    """
    Manages document indexing and retrieval for RAG applications.
    
    Features:
    - Web scraping and document loading
    - Text splitting and chunking
    - Vector embedding and storage
    - Retrieval tool creation
    """
    
    def __init__(self, 
                 embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 vector_size: int = 384):
        """
        Initialize the RAG manager.
        
        Args:
            embedding_model_name: HuggingFace embedding model name
            chunk_size: Size of document chunks
            chunk_overlap: Overlap between chunks
            vector_size: Dimension of embedding vectors
        """
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vector_size = vector_size
        
        self.embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_name)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        
        # In-memory Qdrant client
        self.client = QdrantClient(":memory:")
        self.collections = {}
    
    async def setup_from_urls(self, 
                            urls: List[str], 
                            collection_name: str = "web_docs",
                            css_selector: Dict[str, Any] = None) -> List:
        """
        Setup RAG from web URLs.
        
        Args:
            urls: List of URLs to scrape
            collection_name: Name for the vector collection
            css_selector: CSS selector configuration for scraping
        
        Returns:
            List of retriever tools
        """
        if css_selector is None:
            css_selector = dict(
                class_=("post-content", "post-title", "post-header", "article", "content")
            )
        
        # Load documents from URLs
        loader = WebBaseLoader(
            web_paths=tuple(urls),
            bs_kwargs=dict(parse_only=bs4.SoupStrainer(**css_selector))
        )
        docs = await loader.aload()
        
        return await self._setup_collection(docs, collection_name)
    
    async def setup_from_documents(self, 
                                 documents: List[str], 
                                 collection_name: str = "text_docs") -> List:
        """
        Setup RAG from text documents.
        
        Args:
            documents: List of document texts
            collection_name: Name for the vector collection
        
        Returns:
            List of retriever tools
        """
        # Convert strings to Document objects
        docs = [Document(page_content=doc) for doc in documents]
        
        return await self._setup_collection(docs, collection_name)
    
    async def _setup_collection(self, docs: List[Document], collection_name: str) -> List:
        """
        Internal method to setup a vector collection.
        
        Args:
            docs: List of documents to index
            collection_name: Name for the collection
        
        Returns:
            List of retriever tools
        """
        if not docs:
            return []
        
        # Split documents
        splits = self.text_splitter.split_documents(docs)
        
        # Create collection if it doesn't exist
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )
        except Exception as e:
            # Collection might already exist
            pass
        
        # Create vector store
        vectorstore = QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=self.embedding_model,
        )
        
        # Add documents
        await vectorstore.aadd_documents(splits)
        
        # Store collection reference
        self.collections[collection_name] = vectorstore
        
        # Create retriever tool
        retriever = vectorstore.as_retriever()
        
        retriever_tool = create_retriever_tool(
            retriever,
            f"search_{collection_name}",
            f"Search for information in the {collection_name} knowledge base."
        )
        
        return [retriever_tool]
    
    def add_documents_to_collection(self, 
                                  documents: List[str], 
                                  collection_name: str) -> None:
        """
        Add more documents to an existing collection.
        
        Args:
            documents: List of document texts to add
            collection_name: Name of the existing collection
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} not found")
        
        docs = [Document(page_content=doc) for doc in documents]
        splits = self.text_splitter.split_documents(docs)
        
        # Add to existing vectorstore
        vectorstore = self.collections[collection_name]
        vectorstore.add_documents(splits)
    
    def list_collections(self) -> List[str]:
        """Get list of available collections."""
        return list(self.collections.keys())
    
    def get_retriever(self, collection_name: str):
        """Get a retriever for a specific collection."""
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} not found")
        
        return self.collections[collection_name].as_retriever()


class URLCollectionManager:
    """
    Manages URL collections with unique naming and fast storage.
    Designed for scalable link management from agent conversations.
    """
    
    def __init__(self, storage_file: str = "url_collections.json"):
        self.storage_file = storage_file
        self.url_registry = self._load_registry()
        self.rag_manager = RAGManager()
    
    def _load_registry(self) -> Dict[str, Any]:
        """Load existing URL registry from storage."""
        try:
            import json
            from pathlib import Path
            
            if Path(self.storage_file).exists():
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Sort by name to maintain alphabetical order
                    return dict(sorted(data.items()))
            return {}
        except Exception:
            return {}
    
    def _save_registry(self):
        """Save URL registry to storage with alphabetical ordering."""
        try:
            import json
            
            # Sort by name for consistent alphabetical order
            sorted_registry = dict(sorted(self.url_registry.items()))
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(sorted_registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save registry: {e}")
    
    def _generate_unique_name(self, base_name: str) -> str:
        """
        Generate unique collection name with numbering if duplicates exist.
        Maintains alphabetical order with numbered succession.
        """
        # Clean base name (alphanumeric + underscores only)
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name.lower().strip())
        clean_name = re.sub(r'_+', '_', clean_name).strip('_')
        
        if not clean_name:
            clean_name = "collection"
        
        # Check if name exists
        if clean_name not in self.url_registry:
            return clean_name
        
        # Find next available number in sequence
        counter = 1
        while f"{clean_name}_{counter:09d}" in self.url_registry:
            counter += 1
        
        return f"{clean_name}_{counter:09d}"
    
    async def add_url_collection(self, url: str, name: str, description: str = None) -> str:
        """
        Add a URL to collections with unique naming.
        
        Args:
            url: URL to scrape and index
            name: Desired collection name (will be made unique)
            description: Optional description
            
        Returns:
            Actual collection name used (may have numbers appended)
        """
        # Generate unique collection name
        collection_name = self._generate_unique_name(name)
        
        try:
            # Setup RAG collection from URL
            rag_tools = await self.rag_manager.setup_from_urls(
                urls=[url],
                collection_name=collection_name
            )
            
            # Store in registry
            self.url_registry[collection_name] = {
                "url": url,
                "original_name": name,
                "description": description or f"Collection for {url}",
                "created_at": self._get_timestamp(),
                "collection_name": collection_name,
                "status": "active"
            }
            
            # Save to persistent storage
            self._save_registry()
            
            print(f"✅ Added URL collection: '{collection_name}' from {url}")
            return collection_name
            
        except Exception as e:
            print(f"❌ Failed to create collection '{collection_name}': {e}")
            raise
    
    async def add_multiple_urls(self, url_data: List[Dict[str, str]]) -> Dict[str, str]:
        """
        Add multiple URLs efficiently.
        
        Args:
            url_data: List of dicts with 'url', 'name', and optional 'description'
            
        Returns:
            Dict mapping original names to actual collection names
        """
        results = {}
        
        for item in url_data:
            url = item.get('url')
            name = item.get('name')
            description = item.get('description')
            
            if not url or not name:
                print(f"⚠️ Skipping invalid entry: {item}")
                continue
            
            try:
                actual_name = await self.add_url_collection(url, name, description)
                results[name] = actual_name
            except Exception as e:
                print(f"❌ Failed to add {name}: {e}")
                results[name] = f"ERROR: {str(e)}"
        
        return results
    
    def get_collection_tools(self, collection_name: str) -> List:
        """Get RAG tools for a specific collection."""
        if collection_name not in self.url_registry:
            raise ValueError(f"Collection '{collection_name}' not found")
        
        if collection_name not in self.rag_manager.collections:
            raise ValueError(f"RAG collection '{collection_name}' not initialized")
        
        retriever = self.rag_manager.get_retriever(collection_name)
        from langchain_core.tools import create_retriever_tool
        
        info = self.url_registry[collection_name]
        tool = create_retriever_tool(
            retriever,
            f"search_{collection_name}",
            f"Search {info['description']} (from {info['url']})"
        )
        
        return [tool]
    
    def list_collections(self) -> Dict[str, Any]:
        """List all registered collections."""
        return dict(sorted(self.url_registry.items()))
    
    def search_collections(self, query: str) -> List[str]:
        """Search for collections by name or description."""
        query_lower = query.lower()
        matches = []
        
        for name, info in self.url_registry.items():
            if (query_lower in name.lower() or 
                query_lower in info.get('description', '').lower() or
                query_lower in info.get('url', '').lower()):
                matches.append(name)
        
        return sorted(matches)
    
    def remove_collection(self, collection_name: str) -> bool:
        """Remove a collection from registry and storage."""
        if collection_name in self.url_registry:
            del self.url_registry[collection_name]
            self._save_registry()
            print(f"🗑️ Removed collection: {collection_name}")
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about collections."""
        total = len(self.url_registry)
        active = sum(1 for info in self.url_registry.values() 
                    if info.get('status') == 'active')
        
        return {
            "total_collections": total,
            "active_collections": active,
            "storage_file": self.storage_file,
            "last_updated": self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


# Global collection manager instance
_global_url_manager = None

def get_url_collection_manager(storage_file: str = "url_collections.json") -> URLCollectionManager:
    """Get or create global URL collection manager."""
    global _global_url_manager
    if _global_url_manager is None:
        _global_url_manager = URLCollectionManager(storage_file)
    return _global_url_manager


# Enhanced RAG functions using URL Collection Manager
async def setup_rag_from_url(url: str, name: str, description: str = None) -> List:
    """
    Setup RAG from a single URL with managed collections.
    
    Args:
        url: URL to scrape
        name: Collection name (will be made unique)
        description: Optional description
        
    Returns:
        List of retriever tools
    """
    manager = get_url_collection_manager()
    collection_name = await manager.add_url_collection(url, name, description)
    return manager.get_collection_tools(collection_name)


async def setup_rag_from_urls(url_data: List[Dict[str, str]]) -> Dict[str, List]:
    """
    Setup RAG from multiple URLs.
    
    Args:
        url_data: List of {'url': str, 'name': str, 'description': str}
        
    Returns:
        Dict mapping collection names to their tools
    """
    manager = get_url_collection_manager()
    results = await manager.add_multiple_urls(url_data)
    
    tools_map = {}
    for original_name, actual_name in results.items():
        if not actual_name.startswith("ERROR:"):
            tools_map[actual_name] = manager.get_collection_tools(actual_name)
    
    return tools_map


# Backward compatibility function  
async def setup_rag_tools():
    """Legacy function for backward compatibility."""
    return await setup_rag_from_url(
        url="https://blog.langchain.com/langchain-langgraph-1dot0/",
        name="langchain_blog",
        description="LangChain 1.0 and LangGraph blog post"
    )
