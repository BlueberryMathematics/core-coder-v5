"""
Intelligent Conversation Memory System
=====================================

Provides scalable conversation memory with automatic summarization,
temporal indexing, and RAG-based retrieval for long-term context management.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

try:
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False


@dataclass
class ConversationSummary:
    """Summary of conversation segments for compression."""
    session_id: str
    start_time: datetime
    end_time: datetime
    message_count: int
    topics: List[str]
    key_information: str
    urls_mentioned: List[str]
    summary_text: str
    original_token_count: int
    compressed_token_count: int


class ConversationMemoryManager:
    """
    Intelligent conversation memory with automatic summarization and RAG search.
    """
    
    def __init__(self,
                 unified_storage = None,
                 max_context_tokens: int = 4000,
                 summarization_threshold: int = 2000,
                 compression_ratio: float = 0.3,
                 model_name: str = "openai/gpt-oss-120b",
                 provider: str = "groq"):
        """
        Initialize conversation memory manager.
        
        Args:
            unified_storage: Unified Qdrant storage instance
            max_context_tokens: Maximum tokens in context window
            summarization_threshold: Token count triggering summarization
            compression_ratio: Target compression ratio for summaries
            model_name: Model to use for summarization
            provider: LLM provider for summarization
        """
        if not STORAGE_AVAILABLE:
            raise ImportError("Storage dependencies not available")
        
        if unified_storage is None:
            try:
                from .storage import UnifiedQdrantStorage
                self.unified_storage = UnifiedQdrantStorage()
            except ImportError:
                raise ImportError("Qdrant storage dependencies not available")
        else:
            self.unified_storage = unified_storage
        self.conversation_storage = self.unified_storage.get_conversation_storage()
        self.max_context_tokens = max_context_tokens
        self.summarization_threshold = summarization_threshold
        self.compression_ratio = compression_ratio
        self.model_name = model_name
        self.provider = provider
        
        # In-memory session management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Summarization agent for compression
        self.summarizer = None
        self._init_summarizer()
    
    def _init_summarizer(self):
        """Initialize summarization agent."""
        try:
            from .base import Agent
            self.summarizer = Agent(
                model_name=self.model_name,
                provider=self.provider,
                system_prompt="""You are a conversation summarizer. Your job is to:
1. Extract key topics and important information
2. Identify URLs and resources mentioned
3. Compress conversations while preserving essential context
4. Maintain temporal flow and relationships
5. Focus on actionable insights and decisions made

Format your summaries as structured text that preserves searchable keywords.""",
                temperature=0.1  # Low temperature for consistent summaries
            )
        except Exception as e:
            print(f"⚠️ Summarizer initialization failed: {e}")
            self.summarizer = None
    
    async def add_message(self,
                         session_id: str,
                         message: str,
                         response: str,
                         urls: List[str] = None,
                         metadata: Dict[str, Any] = None) -> str:
        """Add message to conversation memory."""
        timestamp = datetime.now()
        
        # Store in persistent storage
        point_id = await self.conversation_storage.store_message(
            session_id=session_id,
            message=message,
            response=response,
            timestamp=timestamp,
            urls=urls or [],
            metadata=metadata or {}
        )
        
        # Update active session tracking
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "messages": [],
                "token_count": 0,
                "last_activity": timestamp,
                "urls": set(),
                "topics": set()
            }
        
        session = self.active_sessions[session_id]
        session["messages"].append({
            "timestamp": timestamp,
            "message": message,
            "response": response,
            "urls": urls or []
        })
        
        # Estimate token count (rough approximation)
        estimated_tokens = len(f"{message} {response}".split()) * 1.3
        session["token_count"] += estimated_tokens
        session["last_activity"] = timestamp
        
        if urls:
            session["urls"].update(urls)
        
        # Check if summarization is needed
        if session["token_count"] > self.summarization_threshold:
            await self._maybe_summarize_session(session_id)
        
        return point_id
    
    async def _maybe_summarize_session(self, session_id: str):
        """Conditionally summarize session if it exceeds thresholds."""
        if not self.summarizer:
            return
        
        session = self.active_sessions.get(session_id)
        if not session or len(session["messages"]) < 5:  # Need minimum messages
            return
        
        try:
            # Get messages to summarize (oldest half)
            messages_to_summarize = session["messages"][:len(session["messages"])//2]
            
            # Create summarization prompt
            conversation_text = "\n".join([
                f"[{msg['timestamp'].strftime('%H:%M:%S')}] User: {msg['message']}\n"
                f"[{msg['timestamp'].strftime('%H:%M:%S')}] Assistant: {msg['response']}"
                for msg in messages_to_summarize
            ])
            
            # Generate summary
            summary_prompt = f"""Summarize this conversation segment, preserving key information:

{conversation_text}

Extract:
1. Main topics discussed
2. Important decisions or conclusions
3. URLs or resources mentioned
4. Key facts or data points
5. Action items or next steps

Provide a structured summary that maintains searchable context."""
            
            summary_response = self.summarizer.chat(summary_prompt)
            
            # Create summary record
            summary = ConversationSummary(
                session_id=session_id,
                start_time=messages_to_summarize[0]["timestamp"],
                end_time=messages_to_summarize[-1]["timestamp"],
                message_count=len(messages_to_summarize),
                topics=self._extract_topics(summary_response),
                key_information=summary_response,
                urls_mentioned=list(set().union(*[msg.get("urls", []) for msg in messages_to_summarize])),
                summary_text=summary_response,
                original_token_count=int(session["token_count"] * 0.5),
                compressed_token_count=len(summary_response.split())
            )
            
            # Store summary in conversation storage
            # Convert datetime objects to strings for JSON serialization
            summary_dict = asdict(summary)
            summary_dict['start_time'] = summary_dict['start_time'].isoformat()
            summary_dict['end_time'] = summary_dict['end_time'].isoformat()
            
            await self.conversation_storage.store_message(
                session_id=f"{session_id}_summary",
                message="CONVERSATION_SUMMARY",
                response=json.dumps(summary_dict),
                timestamp=datetime.now(),
                metadata={"type": "summary", "original_session": session_id}
            )
            
            # Update session - keep recent messages
            session["messages"] = session["messages"][len(messages_to_summarize):]
            session["token_count"] *= 0.5  # Approximate remaining tokens
            
            print(f"📝 Summarized {len(messages_to_summarize)} messages for session {session_id}")
            
        except Exception as e:
            print(f"❌ Summarization failed: {e}")
    
    def _extract_topics(self, summary_text: str) -> List[str]:
        """Extract topics from summary text."""
        # Simple topic extraction - could be enhanced with NLP
        words = summary_text.lower().split()
        topics = []
        
        # Look for common topic indicators
        topic_indicators = ["about", "regarding", "concerning", "discussing"]
        for i, word in enumerate(words):
            if word in topic_indicators and i + 1 < len(words):
                topics.append(words[i + 1])
        
        # Extract capitalized words as potential topics
        import re
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', summary_text)
        topics.extend(capitalized[:5])  # Limit to top 5
        
        return list(set(topics))[:10]  # Max 10 topics
    
    async def search_memory(self,
                          query: str,
                          session_id: str = None,
                          time_range: Tuple[datetime, datetime] = None,
                          urls: List[str] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversation memory with multiple filters."""
        start_time, end_time = time_range if time_range else (None, None)
        
        results = await self.conversation_storage.search_conversations(
            query=query,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            urls=urls,
            limit=limit
        )
        
        return results
    
    async def get_session_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get structured session history."""
        # Ensure session is loaded
        await self.get_context_for_session(session_id)
        
        session = self.active_sessions.get(session_id)
        if not session:
            return []
            
        return session["messages"][-limit:]

    async def get_context_for_session(self,
                                    session_id: str,
                                    max_tokens: int = None) -> str:
        """Get conversation context for a session with smart truncation."""
        max_tokens = max_tokens or self.max_context_tokens
        
        # Get active session messages
        session = self.active_sessions.get(session_id)
        
        # If session not in memory, try to restore from storage
        if not session:
            try:
                recent_messages = await self.conversation_storage.get_recent_messages(session_id, limit=20)
                if recent_messages:
                    # Reconstruct session in memory
                    self.active_sessions[session_id] = {
                        "messages": recent_messages,
                        "token_count": 0,
                        "last_activity": recent_messages[-1]["timestamp"],
                        "urls": set(),
                        "topics": set()
                    }
                    session = self.active_sessions[session_id]
                    # Recalculate token count
                    for msg in recent_messages:
                        session["token_count"] += len(f"{msg['message']} {msg['response']}".split()) * 1.3
            except Exception as e:
                print(f"⚠️ Failed to restore session context: {e}")
        
        if not session:
            return ""

        messages = session["messages"]
        
        # If within token limit, return recent messages
        if session.get("token_count", 0) <= max_tokens:
            context_parts = []
            for msg in messages[-10:]:  # Last 10 messages
                context_parts.append(f"User: {msg['message']}")
                context_parts.append(f"Assistant: {msg['response']}")
            return "\n\n".join(context_parts)
        
        # Need to search for relevant context
        if messages:
            # Use most recent message as query for context search
            recent_query = messages[-1]["message"]
            relevant_context = await self.search_memory(
                query=recent_query,
                session_id=session_id,
                limit=5
            )
            
            # Build context from search results + recent messages
            context_parts = []
            
            # Add relevant historical context
            for result in relevant_context:
                if result["id"] != f"{session_id}_{messages[-1]['timestamp'].isoformat()}":
                    context_parts.append(f"[Earlier] User: {result['message']}")
                    context_parts.append(f"[Earlier] Assistant: {result['response']}")
            
            # Add recent messages
            for msg in messages[-3:]:  # Last 3 messages
                context_parts.append(f"User: {msg['message']}")
                context_parts.append(f"Assistant: {msg['response']}")
            
            return "\n\n".join(context_parts)
        
        return ""
    
    def get_memory_tools(self) -> List:
        """Get RAG tools for memory search."""
        
        @tool
        def search_conversation_history(query: str, time_range: str = None, session_filter: str = None) -> str:
            """
            Search conversation history using semantic similarity.
            
            Args:
                query: Search query for finding relevant conversations
                time_range: Optional time filter (e.g., "last_week", "today", "2024-01-15")
                session_filter: Optional session ID to limit search scope
            
            Returns:
                Formatted search results with timestamps and relevance scores
            """
            # Parse time range
            time_filter = None
            if time_range:
                now = datetime.now()
                if time_range == "today":
                    time_filter = (now.replace(hour=0, minute=0, second=0), now)
                elif time_range == "last_week":
                    time_filter = (now - timedelta(days=7), now)
                elif time_range == "last_month":
                    time_filter = (now - timedelta(days=30), now)
                else:
                    try:
                        # Try parsing as date
                        date = datetime.fromisoformat(time_range)
                        time_filter = (date, date + timedelta(days=1))
                    except:
                        pass
            
            # Search memory
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.search_memory(
                        query=query,
                        session_id=session_filter,
                        time_range=time_filter,
                        limit=5
                    )
                )
            finally:
                loop.close()
            
            if not results:
                return "No relevant conversation history found."
            
            # Format results
            formatted_results = []
            for result in results:
                timestamp = datetime.fromisoformat(result["timestamp"])
                formatted_results.append(
                    f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] (Score: {result['score']:.2f})\n"
                    f"User: {result['message']}\n"
                    f"Assistant: {result['response'][:200]}..."
                )
            
            return "\n\n".join(formatted_results)
        
        @tool
        def search_by_url_context(url_pattern: str) -> str:
            """
            Find conversations related to specific URLs or domains.
            
            Args:
                url_pattern: URL pattern to search for (can be partial)
            
            Returns:
                Conversations that mentioned or involved the specified URLs
            """
            # Search memory with URL filter
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self.search_memory(
                        query=f"url: {url_pattern}",
                        urls=[url_pattern],
                        limit=10
                    )
                )
            finally:
                loop.close()
            
            if not results:
                return f"No conversations found involving URLs matching '{url_pattern}'."
            
            # Format results
            formatted_results = []
            for result in results:
                timestamp = datetime.fromisoformat(result["timestamp"])
                urls = result.get("urls", [])
                url_list = ", ".join(urls) if urls else "No URLs"
                
                formatted_results.append(
                    f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] URLs: {url_list}\n"
                    f"Context: {result['message'][:150]}..."
                )
            
            return "\n\n".join(formatted_results)
        
        return [search_conversation_history, search_by_url_context]


# Global memory manager
_global_memory_manager = None


def get_memory_manager() -> ConversationMemoryManager:
    """Get global conversation memory manager."""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = ConversationMemoryManager()
    return _global_memory_manager


def create_memory_enhanced_agent(**kwargs):
    """Create an agent with conversation memory capabilities."""
    try:
        from .base import Agent
        
        # Create agent
        agent = Agent(**kwargs)
        
        # Add memory tools
        memory_manager = get_memory_manager()
        memory_tools = memory_manager.get_memory_tools()
        agent.add_tools(memory_tools)
        
        # Enhance agent with memory context
        original_chat = agent.chat
        
        def enhanced_chat(message: str, session_id: str = "default", **kwargs) -> str:
            """Enhanced chat with conversation memory."""
            # Get conversation context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                context = loop.run_until_complete(
                    memory_manager.get_context_for_session(session_id)
                )
                
                # Add context to system prompt if available
                if context:
                    enhanced_message = f"""Previous conversation context:
{context}

Current message: {message}"""
                else:
                    enhanced_message = message
                
                # Get response
                response = original_chat(enhanced_message, **kwargs)
                
                # Store in memory
                loop.run_until_complete(
                    memory_manager.add_message(
                        session_id=session_id,
                        message=message,
                        response=response
                    )
                )
                
                return response
                
            finally:
                loop.close()
        
        # Replace chat method
        agent.chat = enhanced_chat
        
        return agent
        
    except ImportError:
        raise ImportError("Agent dependencies not available")


if __name__ == "__main__":
    # Example usage
    print("🧠 Testing Conversation Memory System...")
    
    memory_manager = get_memory_manager()
    
    # Simulate conversation
    async def test_memory():
        await memory_manager.add_message(
            session_id="test_session",
            message="I'm working on a machine learning project with Python",
            response="That sounds interesting! What type of ML problem are you solving?"
        )
        
        await memory_manager.add_message(
            session_id="test_session", 
            message="It's a classification problem for image recognition",
            response="For image classification, you might want to consider using CNNs with TensorFlow or PyTorch."
        )
        
        # Search memory
        results = await memory_manager.search_memory(
            query="machine learning Python",
            session_id="test_session"
        )
        
        print(f"Found {len(results)} relevant memories")
        for result in results:
            print(f"- {result['message'][:50]}...")
    
    asyncio.run(test_memory())
    print("✅ Memory system test completed")
