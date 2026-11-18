from __future__ import annotations

import compileall
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
            self.in_inline_script = "src" not in dict(attrs)
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
    config = CONFIG.read_text(encoding="utf-8")
    if '<script src="./config.js"></script>' not in html:
        fail("index.html must load config.js before the inline application script")
    if any(term in html.lower() for term in ("getusermedia", "microphone", "micbtn", "id=\"mic\"", "/api/live", "voicemode")):
        fail("microphone/live voice code or UI is still present in index.html")
    if "voiceUrl" in config or "/api/live" in config:
        fail("live voice endpoint is still present in config.js")

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
    if '@app.websocket("/api/live")' in backend_source or "getUserMedia" in backend_source:
        fail("microphone/live voice backend route is still present")

    print("PASS: frontend JavaScript syntax, microphone removal, and Python backend compilation")


if __name__ == "__main__":
    main()
