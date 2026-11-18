from __future__ import annotations

import compileall
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CONFIG = ROOT / "config.js"
BACKEND = ROOT / "backend"


class InlineScriptExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_inline_script = False
        self.parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attrs_map = dict(attrs)
            self.in_inline_script = "src" not in attrs_map
            self.parts = []

    def handle_data(self, data):
        if self.in_inline_script:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_inline_script:
            self.scripts.append("".join(self.parts))
            self.in_inline_script = False
            self.parts = []


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not INDEX.is_file() or not CONFIG.is_file():
        fail("index.html or config.js is missing")

    html = INDEX.read_text(encoding="utf-8")
    if '<script src="./config.js"></script>' not in html:
        fail("index.html must load config.js before the inline application script")
    if "async async function" in html:
        fail("duplicate async keyword found in index.html")
    if "async function activateLiveMic" not in html:
        fail("voice activation handler is missing or not async")
    if 'getUserMedia({ audio: true })' not in html:
        fail("iOS-compatible microphone request is missing")

    parser = InlineScriptExtractor()
    parser.feed(html)
    if len(parser.scripts) != 1 or not parser.scripts[0].strip():
        fail(f"expected one inline application script, found {len(parser.scripts)}")

    try:
        subprocess.run(
            ["node", "--check", "-"],
            input=parser.scripts[0],
            text=True,
            check=True,
            cwd=ROOT,
        )
    except FileNotFoundError:
        fail("Node.js is required to syntax-check the frontend JavaScript")
    except subprocess.CalledProcessError:
        fail("frontend JavaScript syntax check failed")

    if not compileall.compile_dir(str(BACKEND), quiet=1, force=True):
        fail("Python backend compilation failed")

    backend_source = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    for required in ('@app.websocket("/api/live")', 'models/gemini-3.1-flash-live-preview',
                     '"server_connected"', '"gemini_connecting"'):
        if required not in backend_source:
            fail(f"backend Live API check failed: missing {required}")

    print("PASS: frontend JavaScript syntax, iOS mic path, and Python backend compilation")


if __name__ == "__main__":
    main()
