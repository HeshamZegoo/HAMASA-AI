from __future__ import annotations

import compileall
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CONFIG = ROOT / "config.js"
BACKEND = ROOT / "backend"


class LocalAssetParser(HTMLParser):
    def __init__(self) -> None:
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        candidate = values.get("src") if tag.lower() in {"script", "img"} else None
        if tag.lower() == "link" and "stylesheet" in values.get("rel", "").lower().split():
            candidate = values.get("href")
        if candidate:
            parsed = urlparse(candidate)
            if not parsed.scheme and not candidate.startswith(("#", "data:")):
                self.assets.append(parsed.path)


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
    ATTACHMENTS = ROOT / "attachments.js"
    if not INDEX.is_file() or not CONFIG.is_file() or not ATTACHMENTS.is_file():
        fail("index.html, config.js, or attachments.js is missing")

    html = INDEX.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    attachments = ATTACHMENTS.read_text(encoding="utf-8")
    if '<script src="./config.js"></script>' not in html:
        fail("index.html must load config.js before the inline application script")
    if any(term in html.lower() for term in ("getusermedia", "microphone", "micbtn", "id=\"mic\"", "/api/live", "voicemode")):
        fail("microphone/live voice code or UI is still present in index.html")
    if "voiceUrl" in config or "/api/live" in config:
        fail("live voice endpoint is still present in config.js")

    api_match = re.search(r'API_URL:\\s*"([^"]+)"', config)
    if not api_match:
        fail("config.js must define API_URL")
    api_url = urlparse(api_match.group(1))
    if api_url.scheme != "https" or not api_url.netloc:
        fail("the public API_URL must use HTTPS")

    assets = LocalAssetParser()
    assets.feed(html)
    for asset in assets.assets:
        resolved = (ROOT / asset.lstrip("/")).resolve()
        if not resolved.is_file():
            fail(f"referenced frontend asset is missing: {asset}")

    required_routes = {
        "/api/chat": html,
        "/api/transcribe": attachments,
        "/api/tts": html,
        "/api/files/generate": html,
        "/api/auth/signup": html,
        "/api/auth/login": html,
        "/api/auth/me": html,
        "/api/auth/logout": html,
        "/api/chats": html,
        "/api/memory": html,
    }
    backend_source = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    for route, frontend_source in required_routes.items():
        if route not in frontend_source or route not in backend_source:
            fail(f"frontend/backend route contract is incomplete: {route}")

    for extension in ("mp3", "wav", "m4a", "aac", "ogg", "webm"):
        if f'"{extension}"' not in attachments:
            fail(f"audio attachment type is missing: {extension}")
    if "MAX_AUDIO_BYTES" not in attachments or "transcript" not in attachments:
        fail("audio attachments must pass through the transcription endpoint")

    public_sources = html + config + attachments
    if re.search(r'(?:sk-[A-Za-z0-9]{24,}|nvapi-[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{30,}|tvly-[A-Za-z0-9_-]{24,})', public_sources):
        fail("a provider API key pattern was found in public frontend files")

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

    try:
        subprocess.run(
            ["node", "--check", str(ATTACHMENTS)],
            text=True,
            check=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        fail("attachment JavaScript syntax check failed")

    if not compileall.compile_dir(str(BACKEND), quiet=1, force=True):
        fail("Python backend compilation failed")

    if '@app.websocket("/api/live")' in backend_source or "getUserMedia" in backend_source:
        fail("microphone/live voice backend route is still present")

    print("PASS: frontend assets, HTTPS API, tool routes, audio attachments, JavaScript syntax, and backend compilation")


if __name__ == "__main__":
    main()
