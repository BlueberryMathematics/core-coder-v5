"""
Base RAG Tools
==============

Knowledge base and retrieval-augmented generation tools.
Integrates with RAG system for document search and ingestion.

NOTE: These tools connect to rag.py RAGManager for actual functionality.
RAG features require qdrant-client and langchain-huggingface packages.
"""

from langchain_core.tools import tool
from pathlib import Path


@tool
def search_knowledge_base(query: str, category: str = "all", limit: int = 5) -> str:
    """
    Search knowledge base for relevant information.
    
    Args:
        query: Search query
        category: Category filter (or collection name)
        limit: Max results to return
        
    Returns:
        Search results from knowledge base
    """
    try:
        from rag import RAGManager
        
        manager = RAGManager()
        collections = manager.list_collections()
        
        if not collections:
            return "Knowledge base is empty. Use 'ingest_reference_file' to add documents first."
        
        # Search in specified collection or first available
        collection_name = category if category in collections else collections[0]
        retriever = manager.get_retriever(collection_name)
        
        results = retriever.get_relevant_documents(query, k=limit)
        
        if not results:
            return f"No results found for '{query}' in {collection_name}"
        
        formatted = f"Found {len(results)} results in '{collection_name}':\n\n"
        for i, doc in enumerate(results, 1):
            content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            formatted += f"{i}. {content}\n\n"
        
        return formatted
            
    except ImportError:
        return "Knowledge base (RAG) not configured. Install: pip install qdrant-client langchain-huggingface"
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


@tool
def ingest_reference_file(file_path: str, category: str = "custom") -> str:
    """
    Ingest a reference file into the knowledge base.
    
    Args:
        file_path: Path to file to ingest
        category: Category/collection name for the file
        
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        from rag import RAGManager
        import asyncio
        
        manager = RAGManager()
        
        # Read file content
        content = path.read_text(encoding='utf-8')
        
        # Create async function to setup from documents
        async def ingest():
            tools = await manager.setup_from_documents(
                documents=[content],
                collection_name=category
            )
            return tools
        
        # Run async ingestion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ingest())
            return f"✅ Ingested {file_path} into knowledge base category '{category}'"
        finally:
            loop.close()
            
    except ImportError:
        return "RAG system not available. Install: pip install qdrant-client langchain-huggingface"
    except Exception as e:
        return f"Error ingesting file: {str(e)}"


@tool
def get_conversation_summary(session_id: str = "default", last_n: int = 10) -> str:
    """
    Get a summary of recent conversation history.
    
    Args:
        session_id: Session identifier
        last_n: Number of recent messages to summarize
        
    Returns:
        Conversation summary
    """
    try:
        from memory import get_memory_manager
        import asyncio
        
        manager = get_memory_manager()
        
        # Get session history
        async def get_summary():
            history = await manager.get_session_history(session_id, limit=last_n)
            
            if not history:
                return f"No conversation history found for session '{session_id}'"
            
            summary = f"Conversation summary for '{session_id}' (last {len(history)} messages):\n\n"
            for entry in history[-last_n:]:
                summary += f"User: {entry.get('message', '')[:100]}...\n"
                summary += f"Agent: {entry.get('response', '')[:100]}...\n\n"
            
            return summary
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(get_summary())
        finally:
            loop.close()
            
    except ImportError:
        return "Memory system not available. Enable with enable_memory=True in agent config."
    except Exception as e:
        return f"Error getting conversation summary: {str(e)}"


@tool
def search_documentation(query: str, source: str = "all") -> str:
    """
    Search technical documentation from ingested docs.
    
    Args:
        query: Search query
        source: Documentation source/collection name
        
    Returns:
        Documentation search results
    """
    try:
        from rag import RAGManager
        
        manager = RAGManager()
        collections = manager.list_collections()
        
        # Look for documentation collections
        doc_collections = [c for c in collections if 'doc' in c.lower() or c == source]
        
        if not doc_collections:
            return f"No documentation collections found. Available: {', '.join(collections)}"
        
        collection_name = doc_collections[0]
        retriever = manager.get_retriever(collection_name)
        
        results = retriever.get_relevant_documents(query, k=5)
        
        if not results:
            return f"No documentation found for '{query}'"
        
        formatted = f"Documentation for '{query}' from {collection_name}:\n\n"
        for i, doc in enumerate(results, 1):
            formatted += f"{i}. {doc.page_content}\n\n"
        
        return formatted
        
    except ImportError:
        return "RAG system not available. Install: pip install qdrant-client langchain-huggingface"
    except Exception as e:
        return f"Error searching documentation: {str(e)}"
