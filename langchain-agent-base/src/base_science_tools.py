"""
Base Science Tools
==================

Core scientific tools for physics, chemistry, and unit conversions.
"""

from langchain_core.tools import tool


@tool
def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    """
    Convert between units (extensible for more units).
    
    Args:
        value: Numeric value to convert
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Converted value or error message
    """
    conversions = {
        ('m', 'km'): 0.001,
        ('km', 'm'): 1000,
        ('lb', 'kg'): 0.453592,
        ('kg', 'lb'): 2.20462,
        ('f', 'c'): lambda x: (x - 32) * 5/9,
        ('c', 'f'): lambda x: x * 9/5 + 32,
    }
    
    key = (from_unit.lower(), to_unit.lower())
    if key in conversions:
        factor = conversions[key]
        result = factor(value) if callable(factor) else value * factor
        return f"{value} {from_unit} = {result:.4f} {to_unit}"
    
    return f"Conversion from {from_unit} to {to_unit} not supported yet"


@tool
def chemistry_helper(formula: str, operation: str = "molar_mass") -> str:
    """Chemistry calculations (placeholder for chemistry integration).
    
    Args:
        formula: Chemical formula
        operation: Type of calculation
        
    Returns:
        Result or error message
    """
    return f"Chemistry helper for '{formula}' ({operation}) - placeholder for chemistry integration"


@tool
def physics_calculator(calculation: str, **kwargs) -> str:
    """Physics calculations (placeholder for physics integration).
    
    Args:
        calculation: Type of physics calculation
        **kwargs: Parameters for calculation
        
    Returns:
        Result or error message
    """
    return f"Physics calculator for '{calculation}' - placeholder for physics integration"
