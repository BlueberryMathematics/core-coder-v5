"""
Base Math Tools
===============

Core mathematical tools for computational agents.
Includes calculators, equation solvers, and matrix operations.
"""

from langchain_core.tools import tool
import math


@tool
def advanced_calculator(expression: str) -> str:
    """
    Evaluate mathematical expressions safely.
    
    Args:
        expression: Math expression like "2 + 3 * 4" or "sqrt(16)"
        
    Returns:
        Calculated result or error message
    """
    try:
        # Define safe functions
        safe_dict = {
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sum': sum, 'pow': pow,
            'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos,
            'tan': math.tan, 'log': math.log, 'log10': math.log10,
            'exp': math.exp, 'pi': math.pi, 'e': math.e,
        }
        
        # Evaluate safely
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return f"Result: {result}"
    
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def solve_quadratic(a: float, b: float, c: float) -> str:
    """
    Solve quadratic equation ax² + bx + c = 0.
    
    Args:
        a: Coefficient of x²
        b: Coefficient of x
        c: Constant term
        
    Returns:
        Solutions or error message
    """
    try:
        if a == 0:
            return "Error: 'a' cannot be zero in a quadratic equation"
        
        discriminant = b**2 - 4*a*c
        
        if discriminant > 0:
            x1 = (-b + math.sqrt(discriminant)) / (2*a)
            x2 = (-b - math.sqrt(discriminant)) / (2*a)
            return f"Two real solutions: x₁ = {x1:.4f}, x₂ = {x2:.4f}"
        elif discriminant == 0:
            x = -b / (2*a)
            return f"One real solution: x = {x:.4f}"
        else:
            real = -b / (2*a)
            imag = math.sqrt(-discriminant) / (2*a)
            return f"Two complex solutions: x₁ = {real:.4f} + {imag:.4f}i, x₂ = {real:.4f} - {imag:.4f}i"
    
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def matrix_operations(operation: str, matrix_a: str, matrix_b: str = None) -> str:
    """
    Perform matrix operations (placeholder for numpy integration).
    
    Args:
        operation: Operation type (add, multiply, transpose, determinant)
        matrix_a: First matrix as string "[[1,2],[3,4]]"
        matrix_b: Second matrix (for binary operations)
        
    Returns:
        Result or error message
    """
    return f"Matrix operation '{operation}' placeholder. Integrate numpy for full implementation."
