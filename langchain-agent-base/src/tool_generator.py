"""
Tool Generation System
======================

LLM-assisted tool creation for the toolbox system.
Supports generating new tools from natural language descriptions.

Usage:
    from .tool_generator import ToolGenerator
    
    generator = ToolGenerator()
    
    # Generate tool from description
    success, message, tool = generator.generate_tool(
        description="Create a tool that calculates the fibonacci sequence",
        category="math"
    )
    
    # Tool is automatically added to toolbox and ready to use
"""

from typing import Tuple, Optional, Callable, List, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from .toolbox import ToolboxManager, get_toolbox


class ToolGenerator:
    """
    Generate tools using LLM assistance.
    Creates properly formatted @tool functions from natural language descriptions.
    """
    
    SYSTEM_PROMPT = """You are an expert Python developer specializing in creating LangChain tools.

Your task is to generate Python code for tools that follow these requirements:

1. **MUST use @tool decorator** from langchain_core.tools
2. **Type hints** are required for all parameters and return type (usually -> str)
3. **Comprehensive docstring** explaining what the tool does, parameters, and return value
4. **Error handling** with try-except blocks that return error messages as strings
5. **Return strings** not exceptions - tools should never raise errors
6. **No dangerous operations** - no file system access, no subprocess, no eval/exec
7. **Self-contained** - include all necessary imports within the function or at module level

Example of a well-formed tool:

```python
from langchain_core.tools import tool
import math

@tool
def calculate_circle_area(radius: float) -> str:
    \"\"\"
    Calculate the area of a circle given its radius.
    
    Args:
        radius: The radius of the circle (must be positive)
    
    Returns:
        String with the calculated area or error message
    
    Examples:
        calculate_circle_area(5.0) -> "Area of circle with radius 5.0: 78.54 square units"
    \"\"\"
    try:
        if radius < 0:
            return "Error: Radius must be positive"
        
        area = math.pi * radius ** 2
        return f"Area of circle with radius {radius}: {area:.2f} square units"
    
    except Exception as e:
        return f"Error calculating circle area: {str(e)}"
```

Generate ONLY the Python code. Do not include explanations, markdown formatting, or code blocks.
Start with imports, then the @tool decorated function."""

    def __init__(self, 
                 model_name: str = "openai/gpt-oss-120b",
                 temperature: float = 0.2,
                 toolbox: ToolboxManager = None):
        """
        Initialize tool generator.
        
        Args:
            model_name: Groq model to use
            temperature: Creativity level (0-1)
            toolbox: ToolboxManager instance (uses global if not provided)
        """
        self.llm = ChatGroq(model=model_name, temperature=temperature)
        self.toolbox = toolbox or get_toolbox()
    
    def generate_tool(self,
                     description: str,
                     category: str = "generated",
                     tool_name: str = None,
                     examples: List[str] = None,
                     dependencies: List[str] = None,
                     return_code_only: bool = False) -> Tuple[bool, str, Optional[Callable]]:
        """
        Generate a tool from natural language description.
        
        Args:
            description: What the tool should do
            category: Tool category (math, science, coding, business, custom, generated)
            tool_name: Optional specific name for the tool
            examples: Optional usage examples to guide generation
            dependencies: Optional list of required libraries
            return_code_only: If True, return code without adding to toolbox
        
        Returns:
            (success, message, tool_function or code_string)
        """
        # Build detailed prompt
        prompt = f"Create a tool with the following specification:\n\n"
        prompt += f"Description: {description}\n\n"
        
        if tool_name:
            prompt += f"Function name: {tool_name}\n\n"
        
        if examples:
            prompt += f"Usage examples:\n"
            for example in examples:
                prompt += f"- {example}\n"
            prompt += "\n"
        
        if dependencies:
            prompt += f"Required libraries: {', '.join(dependencies)}\n\n"
        
        prompt += f"Category: {category}\n\n"
        prompt += "Generate the complete, working Python code now:"
        
        try:
            # Generate tool code
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            generated_code = response.content.strip()
            
            # Clean up code (remove markdown if present)
            if "```python" in generated_code:
                generated_code = generated_code.split("```python")[1].split("```")[0].strip()
            elif "```" in generated_code:
                generated_code = generated_code.split("```")[1].split("```")[0].strip()
            
            # Return just code if requested
            if return_code_only:
                return True, "Tool code generated", generated_code
            
            # Add to toolbox
            success, message, tool_func = self.toolbox.add_tool_from_code(
                generated_code,
                category=category,
                author="llm",
                version="1.0.0",
                tags=["generated", "llm", category]
            )
            
            if success:
                return True, f"Tool generated and added: {message}", tool_func
            else:
                return False, f"Tool generated but failed to add: {message}\n\nGenerated code:\n{generated_code}", generated_code
        
        except Exception as e:
            return False, f"Error generating tool: {str(e)}", None
    
    def improve_tool(self,
                    tool_name: str,
                    improvements: str) -> Tuple[bool, str, Optional[Callable]]:
        """
        Improve an existing tool based on feedback.
        
        Args:
            tool_name: Name of existing tool to improve
            improvements: Description of what to improve
        
        Returns:
            (success, message, new_tool_function)
        """
        # Get existing tool metadata
        if tool_name not in self.toolbox.registry:
            return False, f"Tool '{tool_name}' not found", None
        
        metadata = self.toolbox.registry[tool_name]
        
        # Read existing code
        from pathlib import Path
        file_path = Path(self.toolbox.toolbox_dir) / metadata.file_path
        if not file_path.exists():
            return False, f"Tool file not found: {file_path}", None
        
        existing_code = file_path.read_text()
        
        # Build improvement prompt
        prompt = f"""Improve the following tool based on this feedback:

{improvements}

Current tool code:
```python
{existing_code}
```

Generate the improved version with the same function name. Maintain backward compatibility where possible."""

        try:
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages)
            improved_code = response.content.strip()
            
            # Clean up code
            if "```python" in improved_code:
                improved_code = improved_code.split("```python")[1].split("```")[0].strip()
            elif "```" in improved_code:
                improved_code = improved_code.split("```")[1].split("```")[0].strip()
            
            # Add improved version (will overwrite with force=True)
            success, message, tool_func = self.toolbox.add_tool_from_code(
                improved_code,
                category=metadata.category,
                author="llm",
                version=self._increment_version(metadata.version),
                tags=metadata.tags + ["improved"],
                force=True
            )
            
            if success:
                return True, f"Tool improved: {message}", tool_func
            else:
                return False, f"Failed to add improved tool: {message}", None
        
        except Exception as e:
            return False, f"Error improving tool: {str(e)}", None
    
    def _increment_version(self, version: str) -> str:
        """Increment version number (e.g., 1.0.0 -> 1.0.1)."""
        parts = version.split('.')
        if len(parts) >= 3:
            parts[2] = str(int(parts[2]) + 1)
            return '.'.join(parts)
        return version
    
    def generate_tool_collection(self,
                                 domain: str,
                                 num_tools: int = 5,
                                 specific_tools: List[str] = None) -> Tuple[bool, str, List[Callable]]:
        """
        Generate a collection of related tools for a domain.
        
        Args:
            domain: Domain description (e.g., "statistics", "linear algebra")
            num_tools: Number of tools to generate
            specific_tools: Optional list of specific tool descriptions
        
        Returns:
            (success, message, list_of_tools)
        """
        tools = []
        
        if specific_tools:
            # Generate specific tools
            for tool_desc in specific_tools:
                success, message, tool_func = self.generate_tool(
                    description=tool_desc,
                    category="generated"
                )
                if success and tool_func:
                    tools.append(tool_func)
        else:
            # Generate general tools for domain
            prompt = f"""List {num_tools} essential tools for the {domain} domain.
            
For each tool, provide:
1. Tool name (as Python function name)
2. Brief description (one sentence)

Format as:
1. tool_name: description
2. tool_name: description
...

Example for 'statistics' domain:
1. calculate_mean: Calculate the arithmetic mean of a list of numbers
2. calculate_standard_deviation: Calculate standard deviation of a dataset
3. calculate_correlation: Calculate correlation coefficient between two datasets

Now list {num_tools} tools for {domain}:"""

            try:
                response = self.llm.invoke([HumanMessage(content=prompt)])
                suggestions = response.content.strip()
                
                # Parse suggestions and generate each tool
                lines = [line.strip() for line in suggestions.split('\n') if line.strip()]
                
                for line in lines[:num_tools]:
                    # Extract tool name and description
                    if ':' in line:
                        parts = line.split(':', 1)
                        tool_desc = parts[1].strip()
                        
                        success, message, tool_func = self.generate_tool(
                            description=tool_desc,
                            category="generated"
                        )
                        
                        if success and tool_func:
                            tools.append(tool_func)
                
            except Exception as e:
                return False, f"Error generating tool collection: {str(e)}", tools
        
        return True, f"Generated {len(tools)} tools for {domain}", tools


class ToolAssistant:
    """
    Interactive assistant for tool management and generation.
    Integrates with agents to provide tool creation during conversations.
    """
    
    def __init__(self, toolbox: ToolboxManager = None):
        """
        Initialize tool assistant.
        
        Args:
            toolbox: ToolboxManager instance
        """
        self.toolbox = toolbox or get_toolbox()
        self.generator = ToolGenerator(toolbox=self.toolbox)
    
    def suggest_tools_for_task(self, task_description: str) -> List[Dict[str, Any]]:
        """
        Analyze a task and suggest relevant tools (existing or to be created).
        
        Args:
            task_description: Description of the task
        
        Returns:
            List of tool suggestions with metadata
        """
        # Search existing tools
        all_tools = self.toolbox.list_tools()
        
        # Simple keyword matching (could be enhanced with embeddings)
        keywords = task_description.lower().split()
        relevant_tools = []
        
        for tool in all_tools:
            tool_text = f"{tool['name']} {tool['description']}".lower()
            relevance_score = sum(1 for kw in keywords if kw in tool_text)
            
            if relevance_score > 0:
                relevant_tools.append({
                    **tool,
                    'relevance': relevance_score,
                    'status': 'existing'
                })
        
        # Sort by relevance
        relevant_tools.sort(key=lambda x: x['relevance'], reverse=True)
        
        return relevant_tools[:5]  # Top 5 suggestions
    
    def create_tool_for_agent(self,
                             agent,
                             tool_description: str,
                             category: str = "custom",
                             add_to_agent: bool = True) -> Tuple[bool, str, Optional[Callable]]:
        """
        Create a tool and optionally add it to an agent.
        
        Args:
            agent: Agent instance to add tool to
            tool_description: What the tool should do
            category: Tool category
            add_to_agent: Whether to add tool to agent immediately
        
        Returns:
            (success, message, tool_function)
        """
        # Generate tool
        success, message, tool_func = self.generator.generate_tool(
            description=tool_description,
            category=category
        )
        
        if success and tool_func and add_to_agent:
            try:
                agent.add_tool(tool_func)
                return True, f"{message}\nTool added to agent.", tool_func
            except Exception as e:
                return True, f"{message}\nWarning: Could not add to agent: {e}", tool_func
        
        return success, message, tool_func
    
    def batch_create_tools(self,
                          tool_descriptions: List[str],
                          category: str = "custom") -> Dict[str, Any]:
        """
        Create multiple tools at once.
        
        Args:
            tool_descriptions: List of tool descriptions
            category: Category for all tools
        
        Returns:
            Results dictionary with created tools
        """
        results = {
            'total': len(tool_descriptions),
            'success': 0,
            'failed': 0,
            'tools': [],
            'errors': []
        }
        
        for desc in tool_descriptions:
            success, message, tool_func = self.generator.generate_tool(
                description=desc,
                category=category
            )
            
            if success:
                results['success'] += 1
                results['tools'].append({
                    'description': desc,
                    'tool': tool_func,
                    'message': message
                })
            else:
                results['failed'] += 1
                results['errors'].append({
                    'description': desc,
                    'error': message
                })
        
        return results


# Convenience functions
def generate_tool(description: str, category: str = "generated", **kwargs) -> Tuple[bool, str, Optional[Callable]]:
    """Generate a tool from description using global generator."""
    generator = ToolGenerator()
    return generator.generate_tool(description, category, **kwargs)


def create_tools_for_domain(domain: str, num_tools: int = 5) -> List[Callable]:
    """Generate a collection of tools for a domain."""
    generator = ToolGenerator()
    success, message, tools = generator.generate_tool_collection(domain, num_tools)
    return tools if success else []


# Example usage
if __name__ == "__main__":
    print("🤖 Testing Tool Generator")
    print("=" * 70)
    
    # Test 1: Generate a simple tool
    print("\n1️⃣ Generating a factorial tool...")
    success, message, tool = generate_tool(
        "Calculate the factorial of a number with proper error handling",
        category="math"
    )
    print(f"   Result: {message}")
    
    if success and tool:
        print(f"   Testing: {tool.invoke({'n': 5})}")
    
    # Test 2: Generate tool collection
    print("\n2️⃣ Generating statistics tools...")
    stats_tools = create_tools_for_domain("statistics", num_tools=3)
    print(f"   Created {len(stats_tools)} statistics tools")
    
    print("\n✅ Tool generator test complete!")
