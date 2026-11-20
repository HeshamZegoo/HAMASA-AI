"""Safe, explicitly allow-listed tools available to HAMASA chat."""
import ast
import asyncio
import ipaddress
import operator
import os
import socket
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlparse

import httpx

from .github_tools import read_public_github_file

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
MAX_PAGE_BYTES = 1_000_000
MAX_PAGE_CHARS = 12_000


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
    result = _number(ast.parse(expression, mode="eval"))
    if not (float("-inf") < result < float("inf")):
        raise ValueError("Result is not finite.")
    rendered = int(result) if result.is_integer() else result
    return {"ok": True, "expression": expression, "result": rendered}


class _ReadableHTML(HTMLParser):
    """Extract readable page text while ignoring scripts, styles, and hidden content."""
    BLOCKED = {"script", "style", "noscript", "svg", "canvas", "template"}
    BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "footer", "li", "h1", "h2", "h3", "h4", "br", "tr"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._blocked = 0
        self._in_title = False
        self._anchor: dict[str, str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.BLOCKED:
            self._blocked += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "a" and attrs.get("href"):
            self._anchor = {"href": attrs["href"][:1000], "text": ""}

    def handle_endtag(self, tag):
        if tag in self.BLOCKED and self._blocked:
            self._blocked -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "a" and self._anchor:
            if self._anchor["text"].strip():
                self.links.append(self._anchor)
            self._anchor = None

    def handle_data(self, data):
        if self._blocked:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.parts.append(clean + " ")
        if self._in_title:
            self.title_parts.append(clean)
        if self._anchor is not None:
            self._anchor["text"] += clean + " "


async def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP and HTTPS webpages can be opened.")
    if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError("Credentials and non-standard ports are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local network addresses are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            records = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80), 0, socket.SOCK_STREAM)
            addresses = {ipaddress.ip_address(record[4][0]) for record in records}
        except (OSError, ValueError) as exc:
            raise ValueError("The webpage hostname could not be resolved.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private, reserved, and local network addresses are blocked.")
    return url


async def open_webpage(url: str) -> dict[str, Any]:
    """Fetch a small public HTML/text page with redirect, size, and SSRF checks."""
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError("A valid webpage URL is required.")
    current = url.strip()
    timeout = httpx.Timeout(18.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False, headers={"User-Agent": "HAMASA-AI-WebReader/1.0", "Accept": "text/html,text/plain,application/xhtml+xml"}) as client:
        for redirect_count in range(4):
            await _validate_public_url(current)
            async with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirect_count == 3:
                        raise ValueError("The webpage redirected too many times.")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise ValueError("This reader currently supports HTML and plain-text webpages only.")
                length = response.headers.get("content-length")
                if length and int(length) > MAX_PAGE_BYTES:
                    raise ValueError("The webpage is too large to read safely.")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_PAGE_BYTES:
                        raise ValueError("The webpage is too large to read safely.")
                charset = response.encoding or "utf-8"
                raw = bytes(chunks).decode(charset, errors="replace")
                if media_type == "text/plain":
                    text = " ".join(raw.split())
                    title = current
                    links = []
                else:
                    parser = _ReadableHTML()
                    parser.feed(raw)
                    text = " ".join(" ".join(parser.parts).split())
                    title = " ".join(parser.title_parts).strip() or current
                    links = [
                        {"text": item["text"].strip()[:160], "url": urljoin(current, item["href"])}
                        for item in parser.links[:20]
                        if urlparse(urljoin(current, item["href"])).scheme in {"http", "https"}
                    ]
                return {
                    "ok": True,
                    "url": current,
                    "title": title[:240],
                    "content": text[:MAX_PAGE_CHARS],
                    "truncated": len(text) > MAX_PAGE_CHARS,
                    "links": links,
                }
    raise ValueError("The webpage could not be opened.")


CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for current facts, sources, prices, documentation, or anything the user asks to research. Return sourced results, not guesses.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "A concise search query."}}, "required": ["query"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_webpage",
            "description": "Open and read a public webpage when search snippets are insufficient. Use the URL from a search result. Returns page title, readable text, and links. Only public HTML/text pages are supported.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "A public HTTP or HTTPS webpage URL."}}, "required": ["url"], "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read a text file from a public GitHub repository when the user asks to inspect public source code or documentation. This is read-only and does not access private repositories or modify code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "GitHub owner or organization."},
                    "repo": {"type": "string", "description": "Repository name."},
                    "path": {"type": "string", "description": "File path inside the repository."},
                    "ref": {"type": "string", "description": "Optional branch, tag, or commit reference; defaults to HEAD."}
                },
                "required": ["owner", "repo", "path"],
                "additionalProperties": False
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute a Python or JavaScript program in a fresh isolated Linux VM when the user asks to run, test, or verify code. Returns actual stdout, stderr, exit code, and timeout status. Only Python and JavaScript are supported; source is limited to 50,000 bytes and execution to 20 seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "javascript"]},
                    "code": {"type": "string", "description": "Complete source code to execute."}
                },
                "required": ["language", "code"],
                "additionalProperties": False
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculate arithmetic accurately. Use for non-trivial calculations instead of mental arithmetic.",
            "parameters": {"type": "object", "properties": {"expression": {"type": "string", "description": "Arithmetic expression using numbers and + - * / // % ** and parentheses."}}, "required": ["expression"], "additionalProperties": False},
        },
    },
]


def code_execution_available() -> bool:
    """Expose code execution only after the private runner and both auth settings are configured."""
    return (
        os.getenv("HAMASA_EXECUTOR_ENABLED", "").strip().lower() == "true"
        and bool(os.getenv("HAMASA_EXECUTOR_URL", "").strip())
        and bool(os.getenv("HAMASA_EXECUTOR_TOKEN", "").strip())
    )


def get_chat_tools() -> list[dict[str, Any]]:
    """Return only tools backed by configured runtime integrations."""
    return [
        tool for tool in CHAT_TOOLS
        if tool["function"]["name"] != "run_code" or code_execution_available()
    ]


def validate_code_request(language: Any, code: Any) -> tuple[str, str]:
    if not isinstance(language, str) or language not in {"python", "javascript"}:
        raise ValueError("Only Python and JavaScript execution are supported.")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Code must be a non-empty string.")
    if len(code.encode("utf-8")) > 50_000:
        raise ValueError("Code exceeds the 50,000-byte limit.")
    return language, code


async def run_isolated_code(language: Any, code: Any) -> dict[str, Any]:
    """Forward source to the private executor; never execute it in this API process."""
    language, code = validate_code_request(language, code)
    if not code_execution_available():
        return {"ok": False, "available": False, "error": "Isolated code execution is not configured."}

    base_url = os.getenv("HAMASA_EXECUTOR_URL", "").strip().rstrip("/")
    token = os.getenv("HAMASA_EXECUTOR_TOKEN", "").strip()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=8.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.post(
                base_url + "/execute",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                json={"language": language, "code": code},
            )
        try:
            result = response.json()
        except ValueError:
            if response.status_code >= 400:
                result = {}
            else:
                return {"ok": False, "error": "The isolated code runner returned an invalid response."}
        if response.status_code >= 400:
            error = result.get("error") if isinstance(result, dict) else None
            return {
                "ok": False,
                "error": str(error or "The isolated code runner rejected the request.")[:240],
                "status_code": response.status_code,
            }
        if not isinstance(result, dict):
            return {"ok": False, "error": "The isolated code runner returned an invalid response."}
        return result
    except httpx.TimeoutException:
        return {"ok": False, "error": "The isolated code runner did not respond before the 45-second deadline."}
    except httpx.RequestError:
        return {"ok": False, "error": "The isolated code runner is temporarily unreachable."}


async def execute_chat_tool(
    name: str,
    arguments: dict[str, Any],
    search: Callable[[str], Awaitable[list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Execute only known tools with validated arguments."""
    if name == "run_code":
        return await run_isolated_code(arguments.get("language"), arguments.get("code"))
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
    if name == "open_webpage":
        url = arguments.get("url")
        if not isinstance(url, str):
            raise ValueError("url must be a string")
        return await open_webpage(url)
    if name == "github_read_file":
        owner, repo, path = arguments.get("owner"), arguments.get("repo"), arguments.get("path")
        ref = arguments.get("ref", "HEAD")
        if not all(isinstance(value, str) for value in (owner, repo, path, ref)):
            raise ValueError("GitHub owner, repo, path, and ref must be strings.")
        return await read_public_github_file(owner, repo, path, ref)
    raise ValueError("Unknown tool.")
