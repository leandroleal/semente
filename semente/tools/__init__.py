"""Engine-neutral tool API — the surface domains use to declare tools.

``tool`` is a native decorator: it returns a :class:`semente.tools.types.Tool`
(description + hooks + the raw function), with no engine import. Each backend
converts ``Tool`` to its own tool type at the boundary. Domains import from
here (or the top-level ``semente`` package) and never from the engine.
"""

from __future__ import annotations

import inspect
import json
import math
from typing import Callable

from semente.tools.types import Audio, File, Image, Tool, ToolResult, Video

__all__ = [
    "tool",
    "Tool",
    "ToolResult",
    "Image",
    "Video",
    "File",
    "Audio",
    "Calculator",
]


def tool(description: str | None = None, tool_hooks: list | None = None, **kwargs) -> Callable:
    """Decorator that declares a domain tool.

    Returns a native :class:`Tool` carrying the raw function (which returns a
    Semente ``ToolResult`` or a plain str/dict), its description, and its hooks.
    The original function is untouched; backends adapt it to their engine.
    """
    del kwargs  # reserved for future engine-agnostic options

    def decorator(func: Callable) -> Tool:
        return Tool(
            name=func.__name__,
            func=func,
            description=description or (inspect.getdoc(func) or "").strip(),
            tool_hooks=list(tool_hooks or []),
        )

    return decorator


# --- Native Calculator toolkit (stdlib only; replaces agno CalculatorTools) ---

def _calc_add(a: float, b: float) -> str:
    """Add two numbers and return the result."""
    return json.dumps({"operation": "addition", "result": a + b})


def _calc_subtract(a: float, b: float) -> str:
    """Subtract the second number from the first and return the result."""
    return json.dumps({"operation": "subtraction", "result": a - b})


def _calc_multiply(a: float, b: float) -> str:
    """Multiply two numbers and return the result."""
    return json.dumps({"operation": "multiplication", "result": a * b})


def _calc_divide(a: float, b: float) -> str:
    """Divide the first number by the second and return the result."""
    if b == 0:
        return json.dumps({"operation": "division", "error": "Division by zero is undefined"})
    return json.dumps({"operation": "division", "result": a / b})


def _calc_exponentiate(a: float, b: float) -> str:
    """Raise the first number to the power of the second and return the result."""
    return json.dumps({"operation": "exponentiation", "result": math.pow(a, b)})


def _calc_square_root(n: float) -> str:
    """Calculate the square root of a number and return the result."""
    if n < 0:
        return json.dumps({"operation": "square_root", "error": "Square root of a negative number is undefined"})
    return json.dumps({"operation": "square_root", "result": math.sqrt(n)})


def _calc_factorial(n: int) -> str:
    """Calculate the factorial of a number and return the result."""
    if n < 0:
        return json.dumps({"operation": "factorial", "error": "Factorial of a negative number is undefined"})
    return json.dumps({"operation": "factorial", "result": math.factorial(n)})


def _calc_is_prime(n: int) -> str:
    """Check if a number is prime and return the result."""
    if n <= 1:
        return json.dumps({"operation": "prime_check", "result": False})
    for i in range(2, int(math.sqrt(n)) + 1):
        if n % i == 0:
            return json.dumps({"operation": "prime_check", "result": False})
    return json.dumps({"operation": "prime_check", "result": True})


_CALCULATOR_FUNCTIONS: dict[str, Tool] = {
    name: Tool(name=name, func=func, description=(inspect.getdoc(func) or "").strip())
    for name, func in {
        "add": _calc_add,
        "subtract": _calc_subtract,
        "multiply": _calc_multiply,
        "divide": _calc_divide,
        "exponentiate": _calc_exponentiate,
        "square_root": _calc_square_root,
        "factorial": _calc_factorial,
        "is_prime": _calc_is_prime,
    }.items()
}


class Calculator:
    """Native calculator toolkit — a bag of ``Tool``s, like agno's CalculatorTools.

    ``functions`` is a ``{name: Tool}`` dict so the shared tool seam
    (``expand_tools``) and the agno backend can both consume it.
    """

    def __init__(self, exclude_tools: list[str] | None = None):
        excluded = set(exclude_tools or [])
        self.functions = {
            name: t for name, t in _CALCULATOR_FUNCTIONS.items() if name not in excluded
        }
