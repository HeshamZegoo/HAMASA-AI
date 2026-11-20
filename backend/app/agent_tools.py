"""Safe, explicitly allow-listed tools available to HAMASA chat."""
import ast
import operator
from typing import Any, Awaitable, Callable

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _number(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _number(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        value = float(node.value)
    elif isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _number(node.left), _number(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("Exponent is too large.")
        value = _BINOPS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        value = _UNARY[type(node.op)](_number(node.operand))
    else:
        raise ValueError("Only basic arithmetic expressions are supported.")
    if abs(value) > 1e100:
        raise ValueError("Result is outside the supported range.")
    return value


def calculate(expression: str) -> dict[str, Any]:
    """Evaluate basic arithmetic without eval(), imports, names, or side effects."""
    expression = expression.strip()
    if not expression or len(expression) > 200:
        raise ValueError("Expression is empty or too long.")
    tree = ast.parse(expression, mode="eval")
    result = _number(tree)
    if not (float("-inf") < result < float("inf")):
        raise ValueError("Result is not finite.")
    rendered = int(result) if result.is_integer() else result
    return {"ok": True, "expression": expression, "result": rendered}


CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for current facts, sources, prices, documentation, or anything the user asks to research. Return sourced results, not guesses.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "A concise search query."}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculate arithmetic accurately. Use for non-trivial calculations instead of mental arithmetic.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Arithmetic expression using numbers and + - * / // % ** and parentheses."}},
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute_chat_tool(
    name: str,
    arguments: dict[str, Any],
    search: Callable[[str], Awaitable[list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Execute only known tools with validated arguments."""
    if name == "calculator":
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            raise ValueError("expression must be a string")
        return calculate(expression)
    if name == "web_search":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        results = await search(query[:400])
        return {
            "ok": bool(results),
            "sources": [
                {
                    "title": str(item.get("title") or "")[:180],
                    "url": str(item.get("url") or "")[:1000],
                    "published_date": str(item.get("published_date") or "")[:40],
                    "content": str(item.get("content") or item.get("raw_content") or "")[:1600],
                }
                for item in results[:8]
            ],
        }
    raise ValueError("Unknown tool.")
